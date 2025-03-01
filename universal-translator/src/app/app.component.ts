import { Component, Inject, ViewChild, ElementRef, OnInit, OnDestroy } from '@angular/core';
import { TranslationService, TranslationRequest, TranslationResponse, StreamedTranslationResponse } from './services/translation.service';
import { AudioRecordingService, RecordingMode } from './services/audio-recording.service';
import { Subscription } from 'rxjs';

// Interface for UI translations
interface UiTranslations {
  title: string;
  streamingMode: string;
  streamingModeDescription: string;
  batchModeDescription: string;
  connected: string;
  disconnected: string;
  audioDevices: string;
  enableAudioTitle: string;
  enableAudioInstructions1: string;
  enableAudioInstructions2: string;
  gotItPlayAudio: string;
  close: string;
  input: string;
  inputPlaceholder: string;
  translate: string;
  startRecording: string;
  stopRecording: string;
  translation: string;
  translationPlaceholder: string;
  streamingHistory: string;
  transcribed: string;
  translated: string;
  noMicrophonesDetected: string;
  noSpeakersDetected: string;
  speakerSelectionNote: string;
  devicePermissionNote: string;
  microphone: string;
  speaker: string;
}

@Component({
  selector: 'app-root',
  templateUrl: './app.component.html',
  styleUrls: ['./app.component.css'],
  standalone: false
})
export class AppComponent implements OnInit, OnDestroy {
  @ViewChild('audioPlayer') audioPlayer!: ElementRef<HTMLAudioElement>;

  // Language toggle properties
  isSpanish = false;
  
  // Define translations
  private englishTranslations: UiTranslations = {
    title: 'Universal Translator',
    streamingMode: 'Live Translation Mode',
    streamingModeDescription: 'Live translation mode is active - translations will appear as you speak. Press the play button above when audio appears.',
    batchModeDescription: 'Standard mode is active - translations will appear after you finish speaking',
    connected: 'Connected',
    disconnected: 'Disconnected',
    audioDevices: 'Audio Devices',
    enableAudioTitle: 'Enable Audio Playback',
    enableAudioInstructions1: 'To hear translations automatically, please tap the "Play" button for this first audio.',
    enableAudioInstructions2: 'After this, future audio responses will play automatically.',
    gotItPlayAudio: 'Got it, play audio',
    close: 'Close',
    input: 'Input',
    inputPlaceholder: 'Enter text to translate...',
    translate: 'Translate Text',
    startRecording: 'Translate Voice',
    stopRecording: 'Stop Voice',
    translation: 'Translation',
    translationPlaceholder: 'Translation will appear here...',
    streamingHistory: 'Streaming History',
    transcribed: 'Transcribed',
    translated: 'Translated',
    noMicrophonesDetected: 'No microphones detected. Please check your connections.',
    noSpeakersDetected: 'No speakers detected. Please check your connections.',
    speakerSelectionNote: 'Note: Speaker selection only works in Chrome, Edge, and Opera. Other browsers will use the system default.',
    devicePermissionNote: 'If device names don\'t appear, you may need to grant persistent audio permission to this site.',
    microphone: 'Microphone',
    speaker: 'Speaker'
  };
  
  private spanishTranslations: UiTranslations = {
    title: 'Traductor Universal',
    streamingMode: 'Modo de Traducción en Vivo',
    streamingModeDescription: 'El modo de traducción en vivo está activo - las traducciones aparecerán mientras hablas. Presiona el botón de reproducción cuando aparezca el audio.',
    batchModeDescription: 'El modo estándar está activo - las traducciones aparecerán después de que termines de hablar',
    connected: 'Conectado',
    disconnected: 'Desconectado',
    audioDevices: 'Dispositivos de audio',
    enableAudioTitle: 'Habilitar reproducción de audio',
    enableAudioInstructions1: 'Para escuchar traducciones automáticamente, toca el botón "Reproducir" para este primer audio.',
    enableAudioInstructions2: 'Después de esto, las futuras respuestas de audio se reproducirán automáticamente.',
    gotItPlayAudio: 'Entendido, reproducir audio',
    close: 'Cerrar',
    input: 'Entrada',
    inputPlaceholder: 'Ingresa texto para traducir...',
    translate: 'Traducir Texto',
    startRecording: 'Traducir Voz',
    stopRecording: 'Detener Voz',
    translation: 'Traducción',
    translationPlaceholder: 'La traducción aparecerá aquí...',
    streamingHistory: 'Historial de transmisión',
    transcribed: 'Transcrito',
    translated: 'Traducido',
    noMicrophonesDetected: 'No se detectaron micrófonos. Por favor, verifica tus conexiones.',
    noSpeakersDetected: 'No se detectaron altavoces. Por favor, verifica tus conexiones.',
    speakerSelectionNote: 'Nota: La selección de altavoces solo funciona en Chrome, Edge y Opera. Otros navegadores usarán el predeterminado del sistema.',
    devicePermissionNote: 'Si los nombres de los dispositivos no aparecen, es posible que debas otorgar permiso de audio persistente a este sitio.',
    microphone: 'Micrófono',
    speaker: 'Altavoz'
  };
  
  // Getter for current translations
  get translations(): UiTranslations {
    return this.isSpanish ? this.spanishTranslations : this.englishTranslations;
  }

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

  // New properties for audio player modal
  showAudioModal = false;
  hasInteractedWithAudio = false;

  // Add these new properties to the class
  private audioQueue: Blob[] = []; // Queue to store pending audio blobs
  private isAudioPlaying = false; // Flag to track if audio is currently playing

  // Add this property for connection polling
  private connectionPollingInterval: any = null;

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

    // Check saved language preference
    const savedLanguage = localStorage.getItem('uiLanguage');
    if (savedLanguage === 'es') {
      this.isSpanish = true;
    }
  }

  toggleStreamingMode() {
    // Determine if we're turning streaming mode on or off
    const enableStreamingMode = !this.isStreamingMode;
    
    // Always stop any existing recording first
    const stopRecordingPromise = this.audioRecordingService.isRecording() 
      ? this.audioRecordingService.stopRecording().catch(error => {
          console.error('Error stopping recording:', error);
        })
      : Promise.resolve();
    
    // After stopping any recording, then update the mode
    stopRecordingPromise.then(() => {
      this.isStreamingMode = enableStreamingMode;
      this.audioRecordingService.setRecordingMode(
        this.isStreamingMode ? RecordingMode.STREAMING : RecordingMode.BATCH
      );
      
      if (this.isStreamingMode) {
        // Clear any previous streaming results
        this.streamedTranscriptions = [];
        
        // Setup WebSocket connection
        this.translationService.connectWebSocket();
        
        // Setup streaming subscription
        this.setupStreamingSubscription();
        
        // Start polling for connection and auto-recording
        this.startConnectionPolling();
        
        // Automatically start recording once in streaming mode
        this.startRecordingIfConnected();
      } else {
        // Disconnect WebSocket
        this.translationService.disconnectWebSocket();
        
        // Stop connection polling
        this.stopConnectionPolling();
      }
    });
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
    // Add the new audio blob to the queue
    this.audioQueue.push(audioBlob);
    
    // If no audio is currently playing, start playing from the queue
    if (!this.isAudioPlaying) {
      this.playNextAudioFromQueue();
    }
  }

  public playNextAudioFromQueue() {
    // If the queue is empty, mark as not playing and return
    if (this.audioQueue.length === 0) {
      this.isAudioPlaying = false;
      return;
    }
    
    // Mark that audio is now playing
    this.isAudioPlaying = true;
    
    // Get the next audio blob from the queue
    const nextAudioBlob = this.audioQueue.shift();
    
    // Revoke previous URL if it exists
    if (this.audioUrl) {
      URL.revokeObjectURL(this.audioUrl);
    }
    
    // Create a new URL for the audio blob
    this.audioUrl = URL.createObjectURL(nextAudioBlob!);
    
    // Play the audio after a short delay to ensure the audio element is updated
    setTimeout(() => {
      if (this.audioPlayer?.nativeElement) {
        // Set the output device first
        if (this.selectedSpeakerId) {
          this.setAudioOutput(this.selectedSpeakerId);
        }
        
        // If user hasn't interacted with audio yet and this is mobile, show the modal
        const isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
        
        if (!this.hasInteractedWithAudio && isMobile) {
          this.showAudioModal = true;
        } else {
          // Try to play automatically if user has interacted before
          this.audioPlayer.nativeElement.play()
            .catch(err => {
              console.warn('Auto-play failed:', err);
              // Mark as not playing so user can manually start
              this.isAudioPlaying = false;
            });
        }
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
      // Display the more detailed error message
      this.errorMessage = error.message || 'Error accessing microphone. Please check permissions.';
      
      // If on iOS, add additional guidance
      if (/iPhone|iPad|iPod/.test(navigator.userAgent)) {
        this.errorMessage += ' On iOS, make sure to grant microphone permissions and check that no other app is using the microphone.';
      }
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

  // Record that the user has interacted with audio - no storage
  onAudioInteraction() {
    this.hasInteractedWithAudio = true;
    this.showAudioModal = false;
    
    // Mark that audio is now playing
    this.isAudioPlaying = true;
    
    // Try to play the audio
    if (this.audioPlayer?.nativeElement) {
      this.audioPlayer.nativeElement.play()
        .catch(err => {
          console.error('Play failed even after interaction:', err);
          this.isAudioPlaying = false; // Reset flag if play fails
        });
    }
  }

  // Close the modal without playing
  closeAudioModal() {
    this.showAudioModal = false;
  }

  // Toggle UI language
  toggleLanguage() {
    this.isSpanish = !this.isSpanish;
    localStorage.setItem('uiLanguage', this.isSpanish ? 'es' : 'en');
  }

  // Add new method to start polling
  private startConnectionPolling() {
    // Clear any existing interval
    this.stopConnectionPolling();
    
    // Poll every second to check connection and recording state
    this.connectionPollingInterval = setInterval(() => {
      this.startRecordingIfConnected();
    }, 1000);
  }

  // Add new method to stop polling
  private stopConnectionPolling() {
    if (this.connectionPollingInterval) {
      clearInterval(this.connectionPollingInterval);
      this.connectionPollingInterval = null;
    }
  }

  // Add new method to start recording if connected
  private startRecordingIfConnected() {
    // Only proceed if we're in streaming mode
    if (!this.isStreamingMode) return;
    
    // Check if WebSocket is connected
    const isConnected = this.translationService.isWebSocketConnected();
    
    // If connected but not recording, start recording
    if (isConnected && !this.audioRecordingService.isRecording()) {
      console.log('WebSocket connected but not recording. Starting recording...');
      this.startRecording();
    }
    // If disconnected but recording, stop recording
    else if (!isConnected && this.audioRecordingService.isRecording()) {
      console.log('WebSocket disconnected but still recording. Stopping recording...');
      this.audioRecordingService.stopRecording().catch(error => {
        console.error('Error stopping recording:', error);
      });
    }
  }

  // More robust status class method
  getStatusClass(): string {
    console.log('Status check - WebSocket connected:', this.translationService.isWebSocketConnected());
    console.log('Status check - Recording active:', this.audioRecordingService.isRecording());
    
    // Need both WebSocket connected AND recording active for green status
    if (this.translationService.isWebSocketConnected() && this.audioRecordingService.isRecording()) {
      return 'connected';
    } else {
      return 'disconnected';
    }
  }

  ngOnDestroy() {
    if (this.audioUrl) {
      URL.revokeObjectURL(this.audioUrl);
    }
    
    this.audioQueue = [];
    
    if (this.streamingSubscription) {
      this.streamingSubscription.unsubscribe();
    }
    if (this.deviceSubscription) {
      this.deviceSubscription.unsubscribe();
    }
    
    // Clean up connection polling
    this.stopConnectionPolling();
  }
}
