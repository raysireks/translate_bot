import { Component, Inject, ViewChild, ElementRef } from '@angular/core';
import { TranslationService, TranslationRequest, TranslationResponse } from './services/translation.service';
import { AudioRecordingService } from './services/audio-recording.service';

@Component({
  selector: 'app-root',
  templateUrl: './app.component.html',
  styleUrls: ['./app.component.css'],
  standalone: false
})
export class AppComponent {
  @ViewChild('audioPlayer') audioPlayer!: ElementRef<HTMLAudioElement>;

  inputText = '';
  translatedText = '';
  isLoading = false;
  errorMessage = '';
  audioUrl: string | null = null;

  constructor(
    @Inject(TranslationService) private translationService: TranslationService,
    @Inject(AudioRecordingService) public audioRecordingService: AudioRecordingService
  ) {}

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
    this.audioRecordingService.startRecording()
      .catch(error => {
        console.error('Recording error:', error);
        this.errorMessage = 'Error accessing microphone. Please check permissions.';
      });
  }

  stopRecording() {
    this.isLoading = true;
    this.audioRecordingService.stopRecording()
      .then(audioBlob => {
        this.translateAudio(audioBlob);
      })
      .catch(error => {
        console.error('Error stopping recording:', error);
        this.errorMessage = 'Error processing recording. Please try again.';
        this.isLoading = false;
      });
  }

  translateAudio(audioBlob: Blob) {
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
          this.audioUrl = URL.createObjectURL(audioBlob);
          
          setTimeout(() => {
            if (this.audioPlayer?.nativeElement) {
              this.audioPlayer.nativeElement.play()
                .catch(err => console.warn('Auto-play failed:', err));
            }
          });
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

  ngOnDestroy() {
    if (this.audioUrl) {
      URL.revokeObjectURL(this.audioUrl);
    }
  }
}
