from fastapi import APIRouter, HTTPException, UploadFile, File, Form, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import logging
from app.service.anthropic import AnthropicService
from app.service.pht import PHT
from app.service.audio_transcription import WhisperHandler, TranscriptionMode
import io
from urllib.parse import quote
import asyncio
import numpy as np
from collections import deque
import json
import wave
import re

# Create logger for this module
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1")
anthropic_service = AnthropicService()

# Create a connection manager for WebSockets
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket connected. Active connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"WebSocket disconnected. Active connections: {len(self.active_connections)}")

manager = ConnectionManager()

# Voice Activity Detection helper class
class SimpleVAD:
    def __init__(self, sample_rate=16000, frame_duration_ms=30, threshold=0.01):
        self.sample_rate = sample_rate
        self.frame_duration_ms = frame_duration_ms
        self.threshold = threshold
        self.frame_size = int(sample_rate * frame_duration_ms / 1000)
        # Number of frames of silence to consider speech segment complete
        self.silence_frames_threshold = 2  # Roughly 450ms of silence

    def is_speech(self, audio_data):
        """Simple energy-based VAD"""
        try:
            # Make sure we have valid data
            if not audio_data or len(audio_data) < 2:
                logger.debug("Received empty or too small audio chunk")
                return False
                
            # Get the buffer length and ensure it's a multiple of 2 (for int16)
            buffer_length = len(audio_data)
            if buffer_length % 2 != 0:
                # If we have an odd number of bytes, trim the last byte
                logger.debug(f"Trimming audio buffer from {buffer_length} to {buffer_length - 1} bytes")
                audio_data = audio_data[:-1]
                buffer_length -= 1
                
            if buffer_length == 0:
                return False
                
            # Convert audio bytes to numpy array (assuming 16-bit PCM)
            audio_array = np.frombuffer(audio_data, dtype=np.int16)
            
            # Calculate energy
            energy = np.mean(np.abs(audio_array)) / 32768.0  # Normalize by max int16 value
            
            # Log energy level for debugging
            if energy > self.threshold:
                logger.debug(f"Speech detected - Energy level: {energy:.4f}")
            
            return energy > self.threshold
        except Exception as e:
            logger.error(f"Error in VAD processing: {str(e)}", exc_info=True)
            return False

class TranslationRequest(BaseModel):
    text: str
    source_language: Optional[str] = None
    target_language: Optional[str] = None

class TranslationResponse(BaseModel):
    translated_text: str
    original_text: str
    detected_language: Optional[str] = None
    transcribed_text: str
    audio_url: Optional[str] = None

class AudioTranslationRequest(BaseModel):
    audio_data: bytes
    detect_language: bool = False

@router.post("/translate/text", response_model=TranslationResponse)
async def translate_text(request: TranslationRequest):
    try:
        translation = await anthropic_service.get_response(user_input=request.text)
        return TranslationResponse(
            translated_text=translation,
            original_text=request.text,
            transcribed_text=request.text
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/translate/audio")
async def translate_audio(
    audio_data: UploadFile = File(...),
    return_audio: bool = True,
    gender: Optional[str] = Form(None),
    language: Optional[str] = Form(None)
):
    
    try:
        # Read uploaded file as bytes
        voice_data = await audio_data.read()
        pht_client = PHT()
        
        # Helper function to return hardcoded gender
        async def get_hardcoded_gender(gender_value):
            """Simple async function to return the provided gender value"""
            return gender_value
        
        # Transcribe the audio
        handler = WhisperHandler(TranscriptionMode.HF.value, model_name="large")
        
        # Use provided gender if available, otherwise detect gender
        if gender:
            logger.info(f"Using provided gender: {gender}")
            gender_task = asyncio.create_task(get_hardcoded_gender(gender))
        else:
            logger.info("Detecting gender from audio")
            gender_task = asyncio.create_task(pht_client.detect_gender(bytearray(voice_data)))
            
        transcribed_text = await handler.transcribe_voice(voice_data)
        logger.info(f"Transcribed text: {transcribed_text}")
        
        if not transcribed_text:
            logger.warning("Empty transcription")
            raise HTTPException(status_code=400, detail="Could not transcribe the audio")
        
        # Translate the transcribed text
        translation = await anthropic_service.get_response(user_input=transcribed_text)
        
        if not translation:
            logger.warning("Empty translation from Anthropic")
            raise HTTPException(status_code=500, detail="Could not get translation")
        
        # Set up response data
        result = {
            "transcribed_text": transcribed_text,
            "translated_text": translation
        }
        
        # Generate TTS response if needed
        if return_audio:
            logger.info("Initializing PHT client for TTS")
            
            try:
                logger.info("Starting TTS generation")
                tts_response = await pht_client.text_to_speech(voice_data, translation, gender_task, language)
                logger.info("TTS generation successful")
                
                # Return audio with text metadata in headers
                audio_bytes = bytes(tts_response)
                audio_buffer = io.BytesIO(audio_bytes)
                audio_buffer.name = "audio.mp3"
                
                return StreamingResponse(
                    audio_buffer, 
                    media_type="audio/mp3",
                    headers={
                        "X-Transcribed-Text": quote(transcribed_text),
                        "X-Translated-Text": quote(translation)
                    }
                )
                
            except Exception as e:
                logger.error(f"TTS generation failed: {str(e)}")
                # Fall back to JSON response if TTS fails
                return JSONResponse(
                    content=result,
                    status_code=200,
                    headers={"X-TTS-Error": quote(str(e))}
                )
        
        # Return JSON if audio not requested
        return JSONResponse(content=result)
            
    except Exception as e:
        logger.error(f"Error in translate_audio: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error processing audio: {str(e)}")

@router.websocket("/ws/stream-audio")
async def websocket_audio_stream(websocket: WebSocket):
    logger.info("WebSocket connection attempt received")
    await manager.connect(websocket)
    vad = SimpleVAD(frame_duration_ms=500, threshold=0.0125)  # Lower threshold for better sensitivity
    
    # Buffer for collecting audio chunks
    audio_buffer = b""
    speech_chunks = []
    silence_frames = 0
    is_speech_active = False
    
    # TEMPORARY: Hardcoded testing mode to limit API calls
    testing_mode = False # Set to True to process only one segment per connection
    processed_segment = False
    
    # Variable to store gender if provided
    provided_gender = None
    provided_language = None
    
    try:
        logger.info("WebSocket connection established for audio streaming")
        await websocket.send_json({"type": "connection_status", "status": "connected"})
        
        # Wait for initial config message that might contain gender or language
        try:
            init_data = await asyncio.wait_for(websocket.receive_json(), timeout=2.0)
            if 'gender' in init_data:
                provided_gender = init_data['gender']
                logger.info(f"Received gender parameter: {provided_gender}")
                await websocket.send_json({
                    "type": "status",
                    "message": f"Using provided gender: {provided_gender}"
                })
            
            if 'language' in init_data:
                provided_language = init_data['language']
                logger.info(f"Received language parameter: {provided_language}")
                await websocket.send_json({
                    "type": "status",
                    "message": f"Using provided language: {provided_language}"
                })
        except (asyncio.TimeoutError, ValueError, TypeError):
            # Continue without parameters if timeout or invalid message
            logger.info("No initial parameters received, will use detection")
            
        async def get_hardcoded_gender(gender_value):
            """Simple async function to return the provided gender value"""
            return gender_value
        
        while True:
            # Receive message from client - handle both text and binary messages
            message = await websocket.receive()
            
            # Check message type
            if "bytes" in message:
                # Process binary audio data
                audio_chunk = message["bytes"]
                
                # Log the size of received chunks for debugging
                logger.debug(f"Received audio chunk of size: {len(audio_chunk)} bytes")
                
                # Check if this frame contains speech
                frame_has_speech = vad.is_speech(audio_chunk)
                
                if frame_has_speech:
                    silence_frames = 0
                    if not is_speech_active:
                        is_speech_active = True
                        logger.debug("Speech detected, starting to collect audio")
                    
                    # Add chunk to the current speech segment
                    speech_chunks.append(audio_chunk)
                else:
                    # No speech detected in this frame
                    if is_speech_active:
                        silence_frames += 1
                        
                        # Still add the silence to the current speech segment (for natural pauses)
                        if silence_frames < vad.silence_frames_threshold:
                            speech_chunks.append(audio_chunk)
                        
                        # If enough silent frames detected, consider this speech segment complete
                        if silence_frames >= vad.silence_frames_threshold and speech_chunks:
                            logger.debug(f"Speech segment complete, processing {len(speech_chunks)} chunks")
                            
                            # Process the complete speech segment
                            complete_audio = b"".join(speech_chunks)
                            
                            # Only process if we have enough audio data (to avoid processing very short noises)
                            if len(complete_audio) > 10000:  # Arbitrary threshold
                                try:
                                    # Send status update to client
                                    await websocket.send_json({
                                        "type": "status",
                                        "message": "Processing speech segment..."
                                    })
                                    
                                    # Convert raw PCM data to WAV format
                                    # Create a BytesIO buffer for the WAV file
                                    wav_buffer = io.BytesIO()
                                    
                                    # Create WAV file with the correct parameters
                                    with wave.open(wav_buffer, 'wb') as wav_file:
                                        wav_file.setnchannels(1)  # Mono
                                        wav_file.setsampwidth(2)  # 2 bytes for int16
                                        wav_file.setframerate(16000)  # Sample rate
                                        wav_file.writeframes(complete_audio)
                                    
                                    # Reset buffer position
                                    wav_buffer.seek(0)
                                    wav_data = wav_buffer.read()
                                    
                                    # Initialize PHT client
                                    pht_client = PHT()
                                    
                                    # Use provided gender if available, otherwise detect gender
                                    if provided_gender:
                                        gender_task = asyncio.create_task(get_hardcoded_gender(provided_gender))
                                        logger.info(f"Using provided gender: {provided_gender}")
                                    else:
                                        gender_task = asyncio.create_task(pht_client.detect_gender(bytearray(wav_data)))
                                        logger.info("Detecting gender from audio")
                                    
                                    # Check and normalize the audio format
                                    if wav_data.startswith(b'RIFF'):
                                        logger.info("Detected WAV format audio data from client")
                                        # WAV format - keep as is, the transcription service can handle it
                                        audio_data = bytearray(wav_data)
                                    else:
                                        logger.info("Detected raw PCM format audio data from client")
                                        # Convert raw PCM to a format the transcription service can handle
                                        audio_data = await convert_pcm_to_audio_format(bytearray(wav_data))
                                    
                                    # Send the normalized audio to the transcription service
                                    handler = WhisperHandler(TranscriptionMode.HF.value, model_name="large")
                                    
                                    transcribed_text = await handler.transcribe_voice(audio_data)
                                    
                                    if transcribed_text:
                                        logger.info(f"Transcribed speech segment: {transcribed_text}")
                                        
                                        # Clean text more thoroughly - strip ALL non-alphanumeric characters
                                        cleaned_text = re.sub(r'[^a-zA-Z\s]', '', transcribed_text.lower()).strip()
                                        words = cleaned_text.split()
                                        
                                        # List of common short phrases we want to FILTER OUT
                                        common_phrases = ["thank you", "gracias"]
                                        
                                        # Check if it's a common phrase we want to ignore
                                        is_common_phrase = any(re.search(r'\b' + re.escape(phrase) + r'\b', cleaned_text) for phrase in common_phrases)
                                        
                                        # Check for highly repetitive content
                                        is_repetitive = False
                                        if len(words) >= 10:  # Only check longer transcriptions
                                            # Count unique words
                                            unique_words = set(words)
                                            # Calculate ratio of unique words to total words
                                            uniqueness_ratio = len(unique_words) / len(words)
                                            
                                            # If less than 20% of words are unique, consider it repetitive
                                            if uniqueness_ratio < 0.2:
                                                is_repetitive = True
                                                logger.info(f"Detected repetitive content with uniqueness ratio: {uniqueness_ratio:.2f}")
                                        
                                        if len(words) <= 1 or is_common_phrase or is_repetitive:
                                            logger.info(f"Ignoring transcription: '{transcribed_text}', cleaned: '{cleaned_text}'")
                                            await websocket.send_json({
                                                "type": "status",
                                                "message": "Ignored transcription (single word, filtered phrase, or repetitive content)"
                                            })
                                            # Reset for the next speech segment
                                            speech_chunks = []
                                            is_speech_active = False
                                            # Skip further processing
                                            continue
                                        
                                        # Translate the transcribed text
                                        translation = await anthropic_service.get_response(user_input=transcribed_text)
                                        
                                        # Send the results back to the client
                                        await websocket.send_json({
                                            "type": "transcription",
                                            "transcribed_text": transcribed_text,
                                            "translated_text": translation
                                        })
                                        
                                        # Optionally generate TTS for the translation
                                        try:
                                            # Use the WAV-formatted audio data instead of the raw PCM data
                                            tts_response = await pht_client.text_to_speech(bytearray(wav_data), translation, gender_task, provided_language)
                                            
                                            # Send the audio back to the client
                                            await websocket.send_bytes(bytes(tts_response))
                                            await websocket.send_json({"type": "audio_complete"})
                                        except Exception as e:
                                            logger.error(f"TTS generation failed: {str(e)}")
                                            await websocket.send_json({
                                                "type": "error",
                                                "message": f"TTS generation failed: {str(e)}"
                                            })
                                    else:
                                        logger.warning("Empty transcription returned")
                                        await websocket.send_json({
                                            "type": "status",
                                            "message": "No speech detected in the audio segment"
                                        })
                                    
                                    # TEMPORARY: Mark segment as processed in testing mode
                                    if testing_mode:
                                        processed_segment = True
                                        await websocket.send_json({
                                            "type": "status", 
                                            "message": "Testing mode: One segment processed. Restart connection for more."
                                        })
                                except Exception as e:
                                    logger.error(f"Error processing speech segment: {str(e)}", exc_info=True)
                                    await websocket.send_json({
                                        "type": "error",
                                        "message": f"Error processing speech: {str(e)}"
                                    })
                            else:
                                logger.debug(f"Audio segment too short ({len(complete_audio)} bytes), ignoring")
                            
                            # Reset for the next speech segment
                            speech_chunks = []
                            is_speech_active = False
            elif "text" in message:
                # Process text message (JSON config)
                try:
                    data = json.loads(message["text"])
                    logger.info(f"Received JSON config: {data}")
                    
                    # Update gender if provided
                    if "gender" in data:
                        provided_gender = data["gender"]
                        logger.info(f"Updated gender parameter: {provided_gender}")
                        await websocket.send_json({
                            "type": "status",
                            "message": f"Updated gender to: {provided_gender}"
                        })
                    
                    # Update language if provided
                    if "language" in data:
                        provided_language = data["language"]
                        logger.info(f"Updated language parameter: {provided_language}")
                        await websocket.send_json({
                            "type": "status",
                            "message": f"Updated language to: {provided_language}"
                        })
                    
                except json.JSONDecodeError:
                    logger.error("Received invalid JSON message")
                    await websocket.send_json({
                        "type": "error",
                        "message": "Invalid configuration format"
                    })
            else:
                logger.warning(f"Received unknown message type: {message}")
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"Error in WebSocket connection: {str(e)}", exc_info=True)
        manager.disconnect(websocket)

async def convert_pcm_to_audio_format(pcm_data: bytearray) -> bytearray:
    """Convert raw PCM audio data to WAV format."""
    logger.info(f"Converting {len(pcm_data)} bytes of PCM data to WAV format")
    try:
        # Process the PCM data asynchronously to avoid blocking
        return await asyncio.to_thread(_create_wav_from_pcm, pcm_data)
    except Exception as e:
        logger.error(f"Error converting PCM to WAV: {str(e)}", exc_info=True)
        # Return the original data if conversion fails
        return pcm_data

def _create_wav_from_pcm(pcm_data: bytearray) -> bytearray:
    """Create a WAV file from PCM data (synchronous function)."""
    # Assume 16-bit mono PCM at 16kHz (adjust parameters if your audio differs)
    sample_rate = 16000
    channels = 1
    sample_width = 2  # 16-bit

    import wave
    import io
    
    wav_buffer = io.BytesIO()
    with wave.open(wav_buffer, 'wb') as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(sample_width)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm_data)
    
    return bytearray(wav_buffer.getvalue())

