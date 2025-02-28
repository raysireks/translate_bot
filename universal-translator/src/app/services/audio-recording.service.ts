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
  private stream: MediaStream | null = null;
  private recorder: MediaRecorder | null = null;
  private audioChunks: Blob[] = [];
  private recordingMode: RecordingMode = RecordingMode.BATCH;
  
  // For raw audio processing
  private audioContext: AudioContext | null = null;
  private scriptProcessor: ScriptProcessorNode | null = null;
  private audioInput: MediaStreamAudioSourceNode | null = null;
  
  private recordingSubject = new BehaviorSubject<boolean>(false);
  public recording$ = this.recordingSubject.asObservable();

  constructor(private webSocketService: WebSocketService) {}

  setRecordingMode(mode: RecordingMode): void {
    this.recordingMode = mode;
  }

  getRecordingMode(): RecordingMode {
    return this.recordingMode;
  }

  startRecording(mode: RecordingMode = RecordingMode.BATCH): Promise<void> {
    this.recordingMode = mode;
    
    if (this.recorder && this.recorder.state === 'recording') {
      return Promise.resolve();
    }

    this.audioChunks = [];
    
    // Connect to WebSocket if in streaming mode
    if (this.recordingMode === RecordingMode.STREAMING) {
      this.webSocketService.connect();
    }
    
    return navigator.mediaDevices.getUserMedia({ 
      audio: {
        channelCount: 1,
        sampleRate: 16000
      }
    })
    .then(stream => {
      this.stream = stream;
      
      if (this.recordingMode === RecordingMode.BATCH) {
        // For batch mode, continue using MediaRecorder
        const options = {
          mimeType: 'audio/webm',
          audioBitsPerSecond: 16000
        };
        
        this.recorder = new MediaRecorder(stream, options);
        
        this.recorder.addEventListener('dataavailable', (event) => {
          if (event.data.size > 0) {
            this.audioChunks.push(event.data);
          }
        });
        
        this.recorder.start(1000);
      } else {
        // For streaming mode, use ScriptProcessorNode to get raw PCM data
        this.setupRawAudioProcessing(stream);
      }
      
      this.recordingSubject.next(true);
    });
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
        if (!this.recorder) {
          reject(new Error('No recorder instance found'));
          return;
        }

        this.recorder.addEventListener('stop', () => {
          const audioBlob = new Blob(this.audioChunks, { type: 'audio/webm' });
          this.cleanupRecording();
          resolve(audioBlob);
        });

        this.recorder.stop();
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

  isRecording(): boolean {
    return this.recordingSubject.value;
  }
} 