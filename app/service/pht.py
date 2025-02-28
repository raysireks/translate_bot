import asyncio
import logging
from pyht import Client, Language
from pyht.client import TTSOptions, Format
from langdetect import detect
from huggingface_hub import InferenceClient
import librosa
import io

from app.config import HF_TOKEN, PLAY_HT_API_KEY, PLAY_HT_USER_ID

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

class PHT:
    def __init__(self):
        self.hf_client = InferenceClient(token=HF_TOKEN)
        self.pht_client = Client(
            user_id=PLAY_HT_USER_ID,
            api_key=PLAY_HT_API_KEY,
        )
        self.gender_task = None

    async def detect_gender(self, audio: bytearray):
        """Detect gender from audio data"""
        try:
            logger.info("Starting gender detection from audio...")
            audio_bytes = bytes(audio)
            result = await asyncio.to_thread(
                self.hf_client.audio_classification,
                audio=audio_bytes,
                model="alefiury/wav2vec2-large-xlsr-53-gender-recognition-librispeech"
            )
            gender = result[0]["label"]
            logger.info(f"Detected gender: {gender}")
            return gender
        except Exception as e:
            logger.error(f"Error during gender detection: {str(e)}", exc_info=True)
            return None

    async def text_to_speech(self, audio: bytearray, text: str, gender_task=None) -> bytearray:
        try:
            logger.info(f"Starting TTS generation for text: {text[:100]}...")
            audio_bytes = bytes(audio)
            
            # Use provided gender task or start a new one if not provided
            if gender_task is None:
                logger.info("No gender task provided, starting gender detection now...")
                gender_task = asyncio.create_task(self.detect_gender(audio))
            
            # Get language
            lang = detect(text)
            logger.info(f"Detected language for TTS: {lang}")
            if lang not in ["es", "en"]:
                lang = "es"
            
            # Define voice settings
            voice_settings = {
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
            
            # Wait for gender detection to complete
            logger.info("Waiting for gender detection to complete...")
            gender = await gender_task
            if gender is None:
                logger.warning("Gender detection failed, defaulting to male")
                gender = "male"
            logger.info(f"Using gender: {gender}")
            
            # Get voice settings based on gender and language
            settings = voice_settings[lang][gender]
            logger.info(f"Using voice settings: {settings}")
            
            options = TTSOptions(
                voice=settings["voice"],
                language=settings["language"],
            )

            logger.info("Starting TTS API call...")
            audio_data = bytearray()
            for chunk in self.pht_client.tts(text, options, voice_engine='Play3.0-mini-http'):
                audio_data.extend(chunk)

            logger.info(f"Successfully generated TTS audio, size: {len(audio_data)} bytes")
            return audio_data

        except Exception as e:
            logger.error(f"Error during TTS generation: {str(e)}", exc_info=True)
            raise

def generate_tts(text: str, voice_id: str = None):
    """Generate text-to-speech audio"""
    client = PHT()
    return client.pht_client.generate_audio(text, voice_id)