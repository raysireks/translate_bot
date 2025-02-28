import { Component, Inject } from '@angular/core';
import { TranslationService, TranslationRequest, TranslationResponse } from './services/translation.service';
import { AudioRecordingService } from './services/audio-recording.service';

@Component({
  selector: 'app-root',
  templateUrl: './app.component.html',
  styleUrls: ['./app.component.css'],
  standalone: false
})
export class AppComponent {
  inputText = '';
  translatedText = '';
  isLoading = false;
  errorMessage = '';

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
    this.translationService.translateAudio(audioBlob).subscribe({
      next: (response: TranslationResponse) => {
        this.inputText = response.original_text;
        this.translatedText = response.translated_text;
        this.isLoading = false;
      },
      error: (error) => {
        console.error('Audio translation error:', error);
        this.errorMessage = 'Error translating audio. Please try again.';
        this.isLoading = false;
      }
    });
  }
}
