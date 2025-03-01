import { Injectable } from '@angular/core';
import { BehaviorSubject, Observable, Subject } from 'rxjs';

export interface WebSocketMessage {
  type: string;
  transcribed_text?: string;
  translated_text?: string;
  message?: string;
  status?: string;
}

@Injectable({
  providedIn: 'root'
})
export class WebSocketService {
  private socket: WebSocket | null = null;
  private connected = new BehaviorSubject<boolean>(false);
  private messageSubject = new Subject<WebSocketMessage>();
  private audioSubject = new Subject<Blob>();
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 3;
  private reconnectTimeoutId: any = null;
  private serverUrl: string;

  // Observable streams
  public connected$ = this.connected.asObservable();
  public messages$ = this.messageSubject.asObservable();
  public audio$ = this.audioSubject.asObservable();

  constructor() {
    // Dynamically construct the WebSocket URL based on the current domain
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host; // Includes hostname and port if present
    this.serverUrl = `${protocol}//${host}/api/v1/ws/stream-audio`;
  }

  /**
   * Set the WebSocket server URL
   * @param url The WebSocket server URL
   */
  setServerUrl(url: string): void {
    console.log('Setting WebSocket server URL:', url);
    this.serverUrl = url;
  }

  /**
   * Get the current WebSocket server URL
   */
  getServerUrl(): string {
    return this.serverUrl;
  }

  connect(): void {
    if (this.socket && (this.socket.readyState === WebSocket.OPEN || this.socket.readyState === WebSocket.CONNECTING)) {
      console.log('WebSocket already connected or connecting');
      return;
    }

    this.cleanup();

    // Create WebSocket connection
    try {
      console.log('Attempting WebSocket connection to:', this.serverUrl);
      this.socket = new WebSocket(this.serverUrl);
      this.socket.binaryType = 'arraybuffer';

      this.socket.onopen = () => {
        console.log('WebSocket connection established successfully');
        this.connected.next(true);
        this.reconnectAttempts = 0; // Reset reconnect attempts on successful connection
      };

      this.socket.onclose = (event) => {
        console.log(`WebSocket connection closed (code: ${event.code}, reason: ${event.reason || 'No reason provided'})`);
        this.connected.next(false);
        
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
          this.attemptReconnect();
        } else {
          this.messageSubject.next({
            type: 'error',
            message: 'WebSocket connection closed after multiple reconnection attempts'
          });
        }
      };

      this.socket.onerror = (error) => {
        console.error('WebSocket error:', error);
        this.connected.next(false);
        this.messageSubject.next({
          type: 'error',
          message: 'WebSocket connection error'
        });
      };

      this.socket.onmessage = (event) => {
        if (event.data instanceof ArrayBuffer) {
          // Handle binary audio data
          const audioBlob = new Blob([event.data], { type: 'audio/mp3' });
          this.audioSubject.next(audioBlob);
        } else {
          // Handle JSON messages
          try {
            const message = JSON.parse(event.data);
            this.messageSubject.next(message);
            
            // Log connection status messages
            if (message.type === 'connection_status') {
              console.log('Connection status:', message.status);
            }
            
            // Log errors
            if (message.type === 'error') {
              console.error('Error from server:', message.message);
            }
          } catch (e) {
            console.error('Error parsing WebSocket message:', e);
          }
        }
      };
    } catch (error) {
      console.error('Error creating WebSocket connection:', error);
      this.messageSubject.next({
        type: 'error',
        message: 'Failed to create WebSocket connection'
      });
    }
  }

  private attemptReconnect(): void {
    this.reconnectAttempts++;
    const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 10000); // Exponential backoff with max 10sec
    
    console.log(`Attempting to reconnect (attempt ${this.reconnectAttempts}) in ${delay}ms...`);
    
    this.reconnectTimeoutId = setTimeout(() => {
      this.connect();
    }, delay);
  }

  disconnect(): void {
    this.cleanup();
  }

  private cleanup(): void {
    // Clear any pending reconnect attempts
    if (this.reconnectTimeoutId) {
      clearTimeout(this.reconnectTimeoutId);
      this.reconnectTimeoutId = null;
    }
    
    // Close the socket if it exists
    if (this.socket) {
      // Only attempt to close if the socket is not already closed
      if (this.socket.readyState !== WebSocket.CLOSED && this.socket.readyState !== WebSocket.CLOSING) {
        try {
          this.socket.close(1000, 'Client disconnected');
        } catch (error) {
          console.error('Error closing WebSocket:', error);
        }
      }
      this.socket = null;
    }
  }

  sendAudio(audioData: ArrayBuffer): void {
    if (this.socket && this.socket.readyState === WebSocket.OPEN) {
      try {
        this.socket.send(audioData);
      } catch (error) {
        console.error('Error sending audio data:', error);
        this.messageSubject.next({
          type: 'error',
          message: 'Failed to send audio data'
        });
      }
    } else {
      console.warn('WebSocket not connected, cannot send audio data');
    }
  }

  isConnected(): boolean {
    return this.connected.value;
  }

  sendConfig(config: any): void {
    if (this.socket && this.socket.readyState === WebSocket.OPEN) {
      try {
        this.socket.send(JSON.stringify(config));
        console.log('Sent configuration to WebSocket:', config);
      } catch (error) {
        console.error('Error sending configuration:', error);
        this.messageSubject.next({
          type: 'error',
          message: 'Failed to send configuration'
        });
      }
    } else {
      console.warn('WebSocket not connected, cannot send configuration');
    }
  }
} 