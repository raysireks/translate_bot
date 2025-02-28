import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

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
}

@Injectable({
  providedIn: 'root'
})
export class TranslationService {
  private apiUrl = 'http://localhost:8080/api/v1';

  constructor(private http: HttpClient) {}

  translateText(request: TranslationRequest): Observable<TranslationResponse> {
    return this.http.post<TranslationResponse>(`${this.apiUrl}/translate/text`, request);
  }

  translateAudio(audioBlob: Blob): Observable<TranslationResponse> {
    const formData = new FormData();
    formData.append('audio_data', audioBlob);
    formData.append('detect_language', 'true');
    
    return this.http.post<TranslationResponse>(`${this.apiUrl}/translate/audio`, formData);
  }
} 