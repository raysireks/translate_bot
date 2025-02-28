from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from typing import Optional
import logging
from app.service.anthropic import AnthropicService
from app.service.pht import PHT
from app.service.audio_transcription import WhisperHandler, TranscriptionMode
import io
from urllib.parse import quote

# Create logger for this module
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1")
anthropic_service = AnthropicService()

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
    return_audio: bool = True
):
    
    try:
        # Read uploaded file as bytes
        voice_data = await audio_data.read()
        
        # Transcribe the audio
        handler = WhisperHandler(TranscriptionMode.HF.value)
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
            pht_client = PHT()
            
            try:
                logger.info("Starting TTS generation")
                tts_response = await pht_client.text_to_speech(voice_data, translation)
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
                logger.error(f"TTS generation failed: {str(e)}", exc_info=True)
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

