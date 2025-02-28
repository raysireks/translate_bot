import { Component, Inject, ViewChild, ElementRef, OnInit, OnDestroy } from '@angular/core';
import { TranslationService, TranslationRequest, TranslationResponse, StreamedTranslationResponse } from './services/translation.service';
import { AudioRecordingService, RecordingMode } from './services/audio-recording.service';
import { Subscription } from 'rxjs';

@Component({
  selector: 'app-root',
  templateUrl: './app.component.html',
  styleUrls: ['./app.component.css'],
  standalone: false
})
export class AppComponent implements OnInit, OnDestroy {
  @ViewChild('audioPlayer') audioPlayer!: ElementRef<HTMLAudioElement>;

  inputText = '';
  translatedText = '';
  isLoading = false;
  errorMessage = '';
  audioUrl: string | null = null;
  
  // Streaming related properties
  isStreamingMode = false;
  streamedTranscriptions: StreamedTranslationResponse[] = [];
  private streamingSubscription: Subscription | null = null;

  // New properties for device selection
  audioInputDevices: MediaDeviceInfo[] = [];
  audioOutputDevices: MediaDeviceInfo[] = [];
  selectedMicrophoneId: string = '';
  selectedSpeakerId: string = '';
  deviceSubscription: Subscription | null = null;
  showDeviceSelector: boolean = false;

  constructor(
    @Inject(TranslationService) public translationService: TranslationService,
    @Inject(AudioRecordingService) public audioRecordingService: AudioRecordingService
  ) {}

  ngOnInit() {
    // Initialize with batch mode by default
    this.audioRecordingService.setRecordingMode(RecordingMode.BATCH);
    
    // Load available audio devices
    this.loadAudioDevices();
    
    // Subscribe to device changes
    this.deviceSubscription = this.audioRecordingService.availableDevices$.subscribe(devices => {
      this.audioInputDevices = devices;
      if (devices.length > 0 && !this.selectedMicrophoneId) {
        this.selectedMicrophoneId = devices[0].deviceId;
      }
    });
  }

  toggleStreamingMode() {
    this.isStreamingMode = !this.isStreamingMode;
    this.audioRecordingService.setRecordingMode(
      this.isStreamingMode ? RecordingMode.STREAMING : RecordingMode.BATCH
    );
    
    if (this.isStreamingMode) {
      // Set up streaming subscription if we're in streaming mode
      this.setupStreamingSubscription();
    } else if (this.streamingSubscription) {
      // Clean up subscription if we're switching back to batch mode
      this.streamingSubscription.unsubscribe();
      this.streamingSubscription = null;
    }
  }

  reconnectWebSocket() {
    this.errorMessage = '';
    this.translationService.connectWebSocket();
    // Try to set up streaming subscription again
    this.setupStreamingSubscription();
  }

  /**
   * Test the WebSocket connection to the server
   * This attempts a new connection and logs detailed information
   * for debugging purposes
   */
  testWebSocketConnection() {
    console.log('Testing WebSocket connection...');
    
    // First disconnect any existing connection
    this.translationService.disconnectWebSocket();
    
    // Clear any existing error message
    this.errorMessage = '';
    
    // Log connection info
    console.log('WebSocket URL:', this.translationService.getWebSocketUrl());
    
    // Try to reconnect
    this.translationService.connectWebSocket();
    
    // Set up a temporary timeout to check connection status
    setTimeout(() => {
      const isConnected = this.translationService.isWebSocketConnected();
      console.log('Connection status after attempt:', isConnected ? 'Connected' : 'Disconnected');
      
      if (!isConnected) {
        this.errorMessage = 'WebSocket connection failed. Check console for details.';
      } else {
        // Show success message
        const prevError = this.errorMessage;
        this.errorMessage = 'WebSocket connection successful!';
        
        // Clear success message after 3 seconds
        setTimeout(() => {
          if (this.errorMessage === 'WebSocket connection successful!') {
            this.errorMessage = prevError;
          }
        }, 3000);
      }
    }, 1000);
  }

  private setupStreamingSubscription() {
    // Unsubscribe if we already have an active subscription
    if (this.streamingSubscription) {
      this.streamingSubscription.unsubscribe();
    }
    
    // Set up new subscription
    this.streamingSubscription = this.translationService.getStreamingResponses().subscribe({
      next: (response: StreamedTranslationResponse) => {
        // Add new transcription to the list
        if (response.transcribed_text || response.translated_text) {
          this.streamedTranscriptions.push(response);
          
          // Update the display with the latest transcription/translation
          if (response.transcribed_text) {
            this.inputText = response.transcribed_text;
          }
          if (response.translated_text) {
            this.translatedText = response.translated_text;
          }
        }
        
        // Play audio if present
        if (response.audio) {
          this.playAudioFromBlob(response.audio);
        }
      },
      error: (error) => {
        console.error('Streaming error:', error);
        this.errorMessage = `Streaming error: ${error}`;
      }
    });
  }

  private playAudioFromBlob(audioBlob: Blob) {
    // Revoke previous URL if it exists
    if (this.audioUrl) {
      URL.revokeObjectURL(this.audioUrl);
    }
    
    // Create a new URL for the audio blob
    this.audioUrl = URL.createObjectURL(audioBlob);
    
    // Play the audio
    setTimeout(() => {
      if (this.audioPlayer?.nativeElement) {
        // Set the output device first
        if (this.selectedSpeakerId) {
          this.setAudioOutput(this.selectedSpeakerId);
        }
        
        // Then play the audio
        this.audioPlayer.nativeElement.play()
          .catch(err => console.warn('Auto-play failed:', err));
      }
    });
  }

  translateText() {
    if (!this.inputText.trim()) {
      this.errorMessage = 'Please enter text to translate';
      return;
    }

    this.isLoading = true;
    this.errorMessage = '';
    
    const request: TranslationRequest = {
      text: this.inputText
    };

    this.translationService.translateText(request).subscribe({
      next: (response: TranslationResponse) => {
        this.translatedText = response.translated_text;
        this.isLoading = false;
      },
      error: (error) => {
        console.error('Translation error:', error);
        this.errorMessage = 'Error translating text. Please try again.';
        this.isLoading = false;
      }
    });
  }

  toggleRecording() {
    if (this.audioRecordingService.isRecording()) {
      this.stopRecording();
    } else {
      this.startRecording();
    }
  }

  startRecording() {
    this.errorMessage = '';
    
    // Clear any previous streaming results if we're in streaming mode
    if (this.isStreamingMode) {
      this.streamedTranscriptions = [];
      this.setupStreamingSubscription();
    }
    
    this.audioRecordingService.startRecording(
      this.isStreamingMode ? RecordingMode.STREAMING : RecordingMode.BATCH
    )
    .catch(error => {
      console.error('Recording error:', error);
      this.errorMessage = 'Error accessing microphone. Please check permissions.';
    });
  }

  stopRecording() {
    // Only show loading indicator in batch mode since streaming already 
    // processes results incrementally
    if (!this.isStreamingMode) {
      this.isLoading = true;
    }
    
    this.audioRecordingService.stopRecording()
      .then(audioBlob => {
        // In streaming mode, we don't need to send the audio blob for processing
        // since it's already been streamed and processed
        if (!this.isStreamingMode) {
          this.translateAudio(audioBlob);
        }
      })
      .catch(error => {
        console.error('Error stopping recording:', error);
        this.errorMessage = 'Error processing recording. Please try again.';
        this.isLoading = false;
      });
  }

  translateAudio(audioBlob: Blob) {
    // Only relevant in batch mode
    this.isLoading = true;
    this.errorMessage = '';
    this.audioUrl = null;

    this.translationService.translateAudio(audioBlob).subscribe({
      next: (response) => {
        const transcribedText = decodeURIComponent(response.headers.get('X-Transcribed-Text') || '');
        const translatedText = decodeURIComponent(response.headers.get('X-Translated-Text') || '');
        
        this.inputText = transcribedText;
        this.translatedText = translatedText;

        if (response.body) {
          const audioBlob = new Blob([response.body], { type: 'audio/mp3' });
          this.playAudioFromBlob(audioBlob);
        }

        this.isLoading = false;
      },
      error: (error) => {
        console.error('Audio translation error:', error);
        this.errorMessage = 'Error translating audio. Please try again.';
        this.isLoading = false;
      }
    });
  }

  toggleDeviceSelector() {
    this.showDeviceSelector = !this.showDeviceSelector;
    if (this.showDeviceSelector) {
      this.loadAudioDevices();
    }
  }
  
  async loadAudioDevices() {
    try {
      // Load microphone input devices
      await this.audioRecordingService.loadAvailableDevices();
      
      // Load speaker output devices
      const devices = await navigator.mediaDevices.enumerateDevices();
      this.audioOutputDevices = devices.filter(device => device.kind === 'audiooutput');
      
      // Select default output device if none is selected
      if (this.audioOutputDevices.length > 0 && !this.selectedSpeakerId) {
        this.selectedSpeakerId = this.audioOutputDevices[0].deviceId;
      }
    } catch (error) {
      console.error('Error loading audio devices:', error);
      this.errorMessage = 'Could not load audio devices. Please check browser permissions.';
    }
  }
  
  onMicrophoneChange(event: Event) {
    const select = event.target as HTMLSelectElement;
    this.selectedMicrophoneId = select.value;
    this.audioRecordingService.setMicrophone(this.selectedMicrophoneId);
  }
  
  onSpeakerChange(event: Event) {
    const select = event.target as HTMLSelectElement;
    this.selectedSpeakerId = select.value;
    
    this.setAudioOutput(this.selectedSpeakerId);
  }

  // New helper method for setting audio output
  setAudioOutput(deviceId: string) {
    // Apply the selected speaker to the audio element if it exists
    if (this.audioPlayer?.nativeElement) {
      // Check if setSinkId is supported
      if ('setSinkId' in HTMLMediaElement.prototype) {
        // Need to cast to any because TypeScript doesn't recognize setSinkId
        (this.audioPlayer.nativeElement as any).setSinkId(deviceId)
          .then(() => {
            console.log(`Successfully set audio output to device: ${deviceId}`);
          })
          .catch((err: any) => {
            console.error('Error setting audio output device:', err);
            this.errorMessage = 'Could not set audio output device. Make sure you\'re using a compatible browser.';
          });
      } else {
        console.warn('setSinkId is not supported in this browser');
        this.errorMessage = 'Your browser doesn\'t support selecting audio output devices.';
      }
    }
  }

  ngOnDestroy() {
    if (this.audioUrl) {
      URL.revokeObjectURL(this.audioUrl);
    }
    
    if (this.streamingSubscription) {
      this.streamingSubscription.unsubscribe();
    }
    if (this.deviceSubscription) {
      this.deviceSubscription.unsubscribe();
    }
  }
}
