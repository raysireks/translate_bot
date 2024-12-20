import asyncio
from io import BytesIO
import logging
import os
from enum import Enum
import re
from huggingface_hub import InferenceClient
from app.config import HF_TOKEN
from pydub import AudioSegment
from faster_whisper import WhisperModel
from typing import Optional
from telegram.ext import ContextTypes
from langdetect import detect


logger = logging.getLogger(__name__)

class TranscriptionMode(Enum):
    LOCAL = "local"
    HF = "hf"

class WhisperHandler:
    def __init__(self, mode: TranscriptionMode, model_name: str = "base"):
        self.mode = mode
        if mode == TranscriptionMode.LOCAL.value:
            WHISPER_MODEL_PATH = os.environ.get("WHISPER_MODEL_PATH", f"/data/models/{model_name}")
            WHISPER_COMPUTE_TYPE = os.environ.get("WHISPER_COMPUTE_TYPE", "int8")
            WHISPER_CPU_THREADS = int(os.environ.get("WHISPER_CPU_THREADS", "16"))
            
            logger.info(f"WHISPER_MODEL_PATH: {WHISPER_MODEL_PATH}")
            logger.info(f"WHISPER_COMPUTE_TYPE: {WHISPER_COMPUTE_TYPE}")
            logger.info(f"WHISPER_CPU_THREADS: {WHISPER_CPU_THREADS}")
            
            self.model = WhisperModelSingleton.get_instance(
                WHISPER_MODEL_PATH, 
                WHISPER_COMPUTE_TYPE, 
                WHISPER_CPU_THREADS
            )
        else:
            if model_name == 'small':
                model = "openai/whisper-small"
            elif model_name == 'large':
                model = "openai/whisper-large-v3-turbo"
            self.client = InferenceClient(
                model,
                token=HF_TOKEN
            )

    
    async def cloneAudioTTS(self, context: ContextTypes.DEFAULT_TYPE, text: str, input_audio):
        client = InferenceClient(token=HF_TOKEN)
        
        lang = detect(text)
        model = "facebook/mms-tts-eng" if lang == 'en' else "facebook/mms-tts-spa"

        result = await asyncio.to_thread(
            client.post,
            model=model,
            json={
                "inputs" : text
            }
        )
        
        return result

    async def transcribe_voice(self, voice_data: bytearray, detect_language: bool = False) -> str:
        # processed_data = await preprocess_audio(voice_data)
        
        if self.mode == TranscriptionMode.LOCAL.value:
            return await self._transcribe_local(voice_data, detect_language)
        return await self._transcribe_hf(voice_data)

    async def _transcribe_local(self, voice_data: bytearray, detect_language: bool) -> str:
        logger.info("transcribing with local")
        import os
        
        # Save to temp file
        temp_path = "temp_audio.raw"
        with open(temp_path, "wb") as f:
            f.write(voice_data)
        
        try:
            segments, info = self.model.transcribe(temp_path)
            detected_lang = info.language
            logger.info(f"Detected language: {detected_lang}")

            if detect_language:
                logger.info("rerunning translation for medium") 
                segments, info = self.model.transcribe(
                    temp_path,
                    language=detected_lang,
                    beam_size=5,
                    temperature=0.0,
                )

            return " ".join([segment.text for segment in segments]).strip()
            
        finally:
            os.remove(temp_path)

    async def _transcribe_hf(self, voice_data: bytearray) -> str:
        logger.info("transcribing with hf")
        return self.client.automatic_speech_recognition(voice_data).text

class WhisperModelSingleton:
    _instance: Optional[WhisperModel] = None
    _model_path: Optional[str] = None

    @classmethod
    def get_instance(cls, model_path: str, compute_type: str = "int8", cpu_threads: int = 16):
        if cls._instance is None or cls._model_path != model_path:
            cls._model_path = model_path
            cls._instance = WhisperModel(
                model_path,
                device="cpu",
                compute_type=compute_type,
                cpu_threads=cpu_threads
            )
        return cls._instance

async def preprocess_audio(audio_bytes: bytearray) -> bytearray:
    logger.info("Preprocessing audio")
    audio = AudioSegment.from_file(BytesIO(audio_bytes)) 
    audio = audio.normalize()
    audio = audio.high_pass_filter(100)
    audio = audio.low_pass_filter(8000)
    audio = audio.set_channels(1) 
    audio = audio.set_frame_rate(16000)
    output = BytesIO()
    audio.export(output, format="wav")
    return bytearray(output.getvalue())