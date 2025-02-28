from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.service.anthropic import AnthropicService
from app.service.pht import PHT
from app.service.audio_transcription import WhisperHandler, TranscriptionMode

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

class AudioTranslationRequest(BaseModel):
    audio_data: bytes
    detect_language: bool = False

@router.post("/translate/text", response_model=TranslationResponse)
async def translate_text(request: TranslationRequest):
    try:
        translation = await anthropic_service.get_response(user_input=request.text)
        return TranslationResponse(
            translated_text=translation,
            original_text=request.text
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/translate/audio", response_model=TranslationResponse)
async def translate_audio(request: AudioTranslationRequest):
    try:
        handler = WhisperHandler(TranscriptionMode.HF.value)
        transcribed_text = await handler.transcribe_voice(request.audio_data, request.detect_language)
        
        if not transcribed_text:
            raise HTTPException(status_code=400, detail="Could not transcribe audio")
            
        translation = await anthropic_service.get_response(user_input=transcribed_text)
        
        # Generate TTS response
        pht_client = PHT()
        tts_response = await pht_client.text_to_speech(request.audio_data, translation)
        
        return TranslationResponse(
            translated_text=translation,
            original_text=transcribed_text,
            audio_response=tts_response
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
