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

    async def text_to_speech(self, audio: bytearray, text: str) -> bytearray:
        try:
            audio_bytes = bytes(audio)
            
            # Get gender
            result = await asyncio.to_thread(
                self.hf_client.audio_classification,
                audio=audio_bytes,
                model="alefiury/wav2vec2-large-xlsr-53-gender-recognition-librispeech"
            )
            gender = result[0]["label"]
            
            # Get emotion and prosody
            emotion_task = asyncio.create_task(asyncio.to_thread(
                self.hf_client.audio_classification,
                audio=audio_bytes,
                model="ehcalabres/wav2vec2-lg-xlsr-en-speech-emotion-recognition"
            ))
            
            # Process speech rate
            y, sr = await asyncio.to_thread(librosa.load, io.BytesIO(audio_bytes))
            onset_env = await asyncio.to_thread(librosa.onset.onset_strength, y=y, sr=sr)
            tempo = await asyncio.to_thread(
                lambda: librosa.beat.tempo(onset_envelope=onset_env, sr=sr)[0]
            )
            speed = tempo / 135.0  # Normalize around typical speech tempo
            speed = max(0.5, min(2.0, speed))
            
            emotion_result = await emotion_task
            
            # Get voice settings
            lang = detect(text)
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
            
            settings = voice_settings[lang][gender]
            
            options = TTSOptions(
                voice=settings["voice"],
                language=settings["language"],
                speed=speed
            )

            logger.info("Starting TTS generation")
            audio_data = bytearray()
            for chunk in self.pht_client.tts(text, options, voice_engine='Play3.0-mini-http'):
                audio_data.extend(chunk)

            logger.info("Succeeded TTS generation")
            return audio_data

        except Exception as e:
            logger.error(f"Error during TTS generation: {str(e)}", exc_info=True)
            raise

def generate_tts(text: str, voice_id: str = None):
    """Generate text-to-speech audio"""
    client = PHT()
    return client.pht_client.generate_audio(text, voice_id)