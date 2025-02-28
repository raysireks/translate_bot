import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, from } from 'rxjs';
import { WebSocketService } from './websocket.service';

export interface TranslationRequest {
  text: string;
  source_language?: string;
  target_language?: string;
}

export interface TranslationResponse {
  translated_text: string;
  original_text: string;
  detected_language?: string;
  audio_response?: any;
  transcribed_text: string;
}

export interface StreamedTranslationResponse {
  transcribed_text: string;
  translated_text: string;
  audio?: Blob;
}

@Injectable({
  providedIn: 'root'
})
export class TranslationService {
  // API configuration
  private apiBaseUrl = 'http://localhost:8080';
  private apiPath = '/api/v1';
  private apiUrl = `${this.apiBaseUrl}${this.apiPath}`;
  
  // WebSocket URL derived from API URL
  private wsBaseUrl: string;

  constructor(
    private http: HttpClient,
    private webSocketService: WebSocketService
  ) {
    // Convert HTTP URL to WebSocket URL
    this.wsBaseUrl = this.apiBaseUrl.replace(/^http/, 'ws');
    // Configure WebSocket service with the correct URL
    this.webSocketService.setServerUrl(`${this.wsBaseUrl}${this.apiPath}/ws/stream-audio`);
  }

  // Get the WebSocket URL for debugging
  getWebSocketUrl(): string {
    return `${this.wsBaseUrl}${this.apiPath}/ws/stream-audio`;
  }

  translateText(request: TranslationRequest): Observable<TranslationResponse> {
    return this.http.post<TranslationResponse>(`${this.apiUrl}/translate/text`, request);
  }

  translateAudio(audioBlob: Blob): Observable<any> {
    const formData = new FormData();
    formData.append('audio_data', audioBlob);
    formData.append('return_audio', 'true');
    
    return this.http.post(`${this.apiUrl}/translate/audio`, formData, {
      responseType: 'blob',
      observe: 'response'
    });
  }

  // Streaming methods that use WebSocket
  getStreamingResponses(): Observable<StreamedTranslationResponse> {
    // Return an observable that emits responses from WebSocket
    return new Observable<StreamedTranslationResponse>(observer => {
      // Handle received text transcriptions and translations
      const messageSubscription = this.webSocketService.messages$.subscribe(message => {
        if (message.type === 'transcription' && message.transcribed_text && message.translated_text) {
          observer.next({
            transcribed_text: message.transcribed_text,
            translated_text: message.translated_text
          });
        } else if (message.type === 'error') {
          observer.error(message.message);
        }
      });

      // Handle received audio
      let lastTranscription: StreamedTranslationResponse | null = null;
      
      const audioSubscription = this.webSocketService.audio$.subscribe(audioBlob => {
        // If we have a previous transcription waiting for audio
        if (lastTranscription) {
          lastTranscription.audio = audioBlob;
          observer.next(lastTranscription);
          lastTranscription = null;
        } else {
          // Just send the audio
          observer.next({
            transcribed_text: '',
            translated_text: '',
            audio: audioBlob
          });
        }
      });

      // Return unsubscribe function
      return () => {
        messageSubscription.unsubscribe();
        audioSubscription.unsubscribe();
      };
    });
  }

  // Initialize WebSocket connection
  connectWebSocket(): void {
    this.webSocketService.connect();
  }

  // Close WebSocket connection
  disconnectWebSocket(): void {
    this.webSocketService.disconnect();
  }

  // Check WebSocket connection status
  isWebSocketConnected(): boolean {
    return this.webSocketService.isConnected();
  }
} 