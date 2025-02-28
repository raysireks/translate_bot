import { Injectable } from '@angular/core';
import { BehaviorSubject, Observable } from 'rxjs';
import { WebSocketService } from './websocket.service';

export enum RecordingMode {
  BATCH = 'batch',
  STREAMING = 'streaming'
}

@Injectable({
  providedIn: 'root'
})
export class AudioRecordingService {
  private mediaRecorder: MediaRecorder | null = null;
  private stream: MediaStream | null = null;
  private recordingSubject = new BehaviorSubject<boolean>(false);
  private recordingMode: RecordingMode = RecordingMode.BATCH;
  
  // Add the missing audioChunks property
  private audioChunks: Blob[] = [];
  
  // New properties for device selection
  private availableDevicesSubject = new BehaviorSubject<MediaDeviceInfo[]>([]);
  private selectedDeviceId: string | null = null;
  
  // For raw audio processing
  private audioContext: AudioContext | null = null;
  private scriptProcessor: ScriptProcessorNode | null = null;
  private audioInput: MediaStreamAudioSourceNode | null = null;
  
  constructor(private webSocketService: WebSocketService) {}

  // Public observable of recording state
  public get recording$(): Observable<boolean> {
    return this.recordingSubject.asObservable();
  }
  
  // New public observable of available devices
  public get availableDevices$(): Observable<MediaDeviceInfo[]> {
    return this.availableDevicesSubject.asObservable();
  }

  public isRecording(): boolean {
    return this.recordingSubject.value;
  }

  public setRecordingMode(mode: RecordingMode): void {
    this.recordingMode = mode;
  }
  
  // New method to get available audio input devices
  public async loadAvailableDevices(): Promise<void> {
    try {
      const devices = await navigator.mediaDevices.enumerateDevices();
      const audioInputDevices = devices.filter(device => device.kind === 'audioinput');
      this.availableDevicesSubject.next(audioInputDevices);
      
      // If no device is selected yet, select the default one
      if (!this.selectedDeviceId && audioInputDevices.length > 0) {
        this.selectedDeviceId = audioInputDevices[0].deviceId;
      }
    } catch (error) {
      console.error('Error loading audio devices:', error);
    }
  }
  
  // New method to set the selected microphone
  public setMicrophone(deviceId: string): void {
    this.selectedDeviceId = deviceId;
    
    // If we're currently recording, stop and restart with the new device
    if (this.isRecording()) {
      this.stopRecording().then(() => {
        this.startRecording(this.recordingMode);
      }).catch(error => {
        console.error('Error restarting recording with new device:', error);
      });
    }
  }

  public async startRecording(mode: RecordingMode): Promise<void> {
    if (this.mediaRecorder && this.isRecording()) {
      console.warn('Recording already in progress');
      return;
    }

    try {
      // Use the selected device if available
      const constraints: MediaStreamConstraints = {
        audio: this.selectedDeviceId ? { deviceId: { exact: this.selectedDeviceId } } : true
      };
      
      this.stream = await navigator.mediaDevices.getUserMedia(constraints);
      
      this.mediaRecorder = new MediaRecorder(this.stream);
      this.recordingSubject.next(true);
      this.recordingMode = mode;

      this.audioChunks = [];
      
      // Connect to WebSocket if in streaming mode
      if (this.recordingMode === RecordingMode.STREAMING) {
        this.webSocketService.connect();
      }
      
      if (this.recordingMode === RecordingMode.BATCH) {
        // For batch mode, continue using MediaRecorder
        const options = {
          mimeType: 'audio/webm',
          audioBitsPerSecond: 16000
        };
        
        this.mediaRecorder = new MediaRecorder(this.stream, options);
        
        this.mediaRecorder.addEventListener('dataavailable', (event) => {
          if (event.data.size > 0) {
            this.audioChunks.push(event.data);
          }
        });
        
        this.mediaRecorder.start(1000);
      } else {
        // For streaming mode, use ScriptProcessorNode to get raw PCM data
        this.setupRawAudioProcessing(this.stream);
      }
    } catch (error) {
      console.error('Error starting recording:', error);
      throw error;
    }
  }

  private setupRawAudioProcessing(stream: MediaStream): void {
    // Create AudioContext
    this.audioContext = new (window.AudioContext || (window as any).webkitAudioContext)({
      sampleRate: 16000,
    });
    
    // Create audio source
    this.audioInput = this.audioContext.createMediaStreamSource(stream);
    
    // Buffer size must be a multiple of the sample size (16-bit = 2 bytes)
    // and should be a power of 2 for efficiency
    const bufferSize = 4096;
    
    // Create ScriptProcessorNode
    this.scriptProcessor = this.audioContext.createScriptProcessor(bufferSize, 1, 1);
    
    // Set up audio processing callback
    this.scriptProcessor.onaudioprocess = (audioProcessingEvent) => {
      if (!this.recordingSubject.value) return;
      
      // Get raw audio data from input channel
      const inputBuffer = audioProcessingEvent.inputBuffer;
      const inputData = inputBuffer.getChannelData(0);
      
      // Convert float32 audio data to int16 for the backend
      const pcmData = new Int16Array(inputData.length);
      for (let i = 0; i < inputData.length; i++) {
        // Convert float32 (-1.0 to 1.0) to int16 (-32768 to 32767)
        pcmData[i] = Math.min(1, Math.max(-1, inputData[i])) * 32767;
      }
      
      // Send raw PCM data to backend
      this.webSocketService.sendAudio(pcmData.buffer);
    };
    
    // Connect nodes
    this.audioInput.connect(this.scriptProcessor);
    this.scriptProcessor.connect(this.audioContext.destination);
  }

  stopRecording(): Promise<Blob> {
    return new Promise((resolve, reject) => {
      if (this.recordingMode === RecordingMode.BATCH) {
        // Batch mode - stop MediaRecorder
        if (!this.mediaRecorder) {
          reject(new Error('No recorder instance found'));
          return;
        }

        this.mediaRecorder.addEventListener('stop', () => {
          const audioBlob = new Blob(this.audioChunks, { type: 'audio/webm' });
          this.cleanupRecording();
          resolve(audioBlob);
        });

        this.mediaRecorder.stop();
      } else {
        // Streaming mode - clean up audio processing nodes
        this.cleanupRecording();
        
        // Return an empty blob since we've already streamed the audio
        resolve(new Blob([], { type: 'audio/webm' }));
      }
    });
  }

  private cleanupRecording(): void {
    // Clean up WebSocket if in streaming mode
    if (this.recordingMode === RecordingMode.STREAMING) {
      this.webSocketService.disconnect();
      
      // Clean up audio processing nodes
      if (this.scriptProcessor) {
        this.scriptProcessor.disconnect();
        this.scriptProcessor = null;
      }
      
      if (this.audioInput) {
        this.audioInput.disconnect();
        this.audioInput = null;
      }
      
      if (this.audioContext && this.audioContext.state !== 'closed') {
        this.audioContext.close().catch(err => console.error('Error closing AudioContext:', err));
        this.audioContext = null;
      }
    }
    
    // Stop all media tracks
    this.stopStream();
    this.recordingSubject.next(false);
  }

  private stopStream() {
    if (this.stream) {
      this.stream.getTracks().forEach(track => track.stop());
      this.stream = null;
    }
  }

  getRecordingMode(): RecordingMode {
    return this.recordingMode;
  }
} 