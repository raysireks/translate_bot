import unittest
from unittest.mock import Mock, patch
from app.service.audio_transcription import AudioTranscription

class TestAudioTranscription(unittest.TestCase):
    def setUp(self):
        self.transcription = AudioTranscription()
    
    @patch('app.service.audio_transcription.whisper')
    def test_transcribe_audio(self, mock_whisper):
        # Mock whisper response
        mock_whisper.load_model.return_value = Mock()
        mock_whisper.load_model.return_value.transcribe.return_value = {
            'text': 'transcribed text'
        }
        
        # Test audio transcription
        audio_data = b'fake_audio_data'
        result = self.transcription.transcribe(audio_data)
        
        self.assertIsInstance(result, str)
        self.assertEqual(result, 'transcribed text') 