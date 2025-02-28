import { Injectable } from '@angular/core';
import { BehaviorSubject, Observable } from 'rxjs';

@Injectable({
  providedIn: 'root'
})
export class AudioRecordingService {
  private stream: MediaStream | null = null;
  private recorder: MediaRecorder | null = null;
  private audioChunks: Blob[] = [];
  
  private recordingSubject = new BehaviorSubject<boolean>(false);
  public recording$ = this.recordingSubject.asObservable();

  constructor() {}

  startRecording(): Promise<void> {
    if (this.recorder && this.recorder.state === 'recording') {
      return Promise.resolve();
    }

    this.audioChunks = [];
    
    return navigator.mediaDevices.getUserMedia({ audio: true })
      .then(stream => {
        this.stream = stream;
        this.recorder = new MediaRecorder(stream);
        
        this.recorder.addEventListener('dataavailable', (event) => {
          if (event.data.size > 0) {
            this.audioChunks.push(event.data);
          }
        });
        
        this.recorder.start();
        this.recordingSubject.next(true);
      });
  }

  stopRecording(): Promise<Blob> {
    return new Promise((resolve, reject) => {
      if (!this.recorder) {
        reject(new Error('No recorder instance found'));
        return;
      }

      this.recorder.addEventListener('stop', () => {
        const audioBlob = new Blob(this.audioChunks, { type: 'audio/webm' });
        this.stopStream();
        this.recordingSubject.next(false);
        resolve(audioBlob);
      });

      this.recorder.stop();
    });
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