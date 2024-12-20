import asyncio
import logging
from pyht import Client, Language
from pyht.client import TTSOptions, Format
from langdetect import detect
from huggingface_hub import InferenceClient
import librosa
import io

from app.config import HF_TOKEN

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('tts_generation.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

async def generate_tts(audio: bytearray, text: str) -> bytearray:
    try:
        client = InferenceClient(token=HF_TOKEN)
        audio_bytes = bytes(audio)
        async def get_gender():
            result = await asyncio.to_thread(
                client.audio_classification,
                audio=audio_bytes,
                model="alefiury/wav2vec2-large-xlsr-53-gender-recognition-librispeech"
            )
            return result[0]["label"]
    
        gender = await get_gender()
        
        async def get_emotion_and_prosody(audio_bytes, client):
            # Run emotion model
            emotion_task = asyncio.create_task(asyncio.to_thread(
                client.audio_classification,
                audio=audio_bytes,
                model="ehcalabres/wav2vec2-lg-xlsr-en-speech-emotion-recognition"
            ))
            
            # Process speech rate with librosa
            async def get_speech_rate():
                audio_io = io.BytesIO(audio_bytes)
                y, sr = librosa.load(audio_io)
                
                onset_env = librosa.onset.onset_strength(y=y, sr=sr)
                tempo = librosa.beat.tempo(onset_envelope=onset_env, sr=sr)[0]
                
                speed = tempo / 135.0  # Normalize around typical speech tempo
                return max(0.5, min(2.0, speed))
            
            # Run both operations concurrently
            emotion_result, speed = await asyncio.gather(
                emotion_task,
                asyncio.to_thread(get_speech_rate)
            )
            
            logger.info(f"Detected emotion: {emotion_result[0]['label']}, speed: {speed}")
            
            return emotion_result[0]["label"], speed
        
        emotion, speed = await get_emotion_and_prosody(audio_bytes, client)
        
        lang_dict = {
            "es": {
                "male": {
                    "language": Language.SPANISH,
                    "voice": "s3://voice-cloning-zero-shot/4e04ebd7-c15a-4085-8b3d-bc919e761178/original/manifest.json"
                },
                "female": {
                    "language": Language.SPANISH,
                    "voice": "s3://voice-cloning-zero-shot/0daf0c04-4640-4f57-92c8-22c2c045a7e3/original/manifest.json"
                }
            },
            "en": {
                "male": {
                    "language": Language.ENGLISH,
                    "voice": "s3://voice-cloning-zero-shot/8bcb20e7-a545-4d13-bb5c-6cf829e1cfc9/original/manifest.json"
                },
                "female": {
                    "language": Language.ENGLISH,
                    "voice": "s3://voice-cloning-zero-shot/0daf0c04-4640-4f57-92c8-22c2c045a7e3/original/manifest.json"
                }
            }
        }
        
        logger.info(f"Detecting language for text: {text[:50]}...")
        lang = detect(text)
        logger.info(f"Detected language: {lang}, gender: {gender}")
        language = lang_dict[lang][gender]["language"]
        voice = lang_dict[lang][gender]["voice"] 
        logger.info(f"Using {language} with {gender} voice")

        logger.info("Initializing PyHT client")
        client = Client(
            user_id="N3FVIUVJ3id35XU4t5gPXsaBrUt2",
            api_key="86e1410f7aa247a281fb46a56ef744ad",
        )

        logger.info("Setting up TTS options")
        options = TTSOptions(
            voice=voice,
            language=language,
            speed=speed
        )

        logger.info("Starting TTS generation")
        audio_data = bytearray()
        for chunk in client.tts(text, options, voice_engine='Play3.0-mini-http'):
            audio_data.extend(chunk)

        logger.info("Succeeded TTS generation")
        return audio_data

    except Exception as e:
        logger.error(f"Error during TTS generation: {str(e)}", exc_info=True)
        raise