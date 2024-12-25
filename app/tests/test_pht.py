import unittest
from unittest.mock import Mock, patch
from app.service.pht import PHT
import pytest
from app.config import PLAY_HT_API_KEY, PLAY_HT_USER_ID

class TestPHT(unittest.TestCase):
    def setUp(self):
        self.pht = PHT()
        
        # Ensure required credentials are set
        self.assertTrue(PLAY_HT_API_KEY, 'PLAY_HT_API_KEY not set in config')
        self.assertTrue(PLAY_HT_USER_ID, 'PLAY_HT_USER_ID not set in config')
    
    @patch('app.service.pht.InferenceClient')
    @patch('app.service.pht.Client')
    @patch('app.service.pht.librosa')
    @patch('app.service.pht.detect')
    async def test_text_to_speech(self, mock_detect, mock_librosa, mock_pht_client, mock_hf_client):
        # Mock the gender classification
        mock_hf_instance = Mock()
        mock_hf_instance.audio_classification.return_value = [{"label": "male"}]
        mock_hf_client.return_value = mock_hf_instance
        
        # Mock librosa audio processing
        mock_librosa.load.return_value = (None, None)
        mock_librosa.onset.onset_strength.return_value = None
        mock_librosa.beat.tempo.return_value = [120.0]
        
        # Mock language detection
        mock_detect.return_value = "en"
        
        # Mock Play.ht client
        mock_client_instance = Mock()
        mock_client_instance.tts.return_value = [b"audio", b"data"]
        mock_pht_client.return_value = mock_client_instance
        
        # Test input
        text = "Hello, this is a test."
        dummy_audio = bytearray(b"dummy audio data")
        
        # Run the function
        result = await self.pht.text_to_speech(dummy_audio, text)
        
        # Verify the result
        self.assertIsInstance(result, bytearray)
        self.assertEqual(result, bytearray(b"audiodata"))
        
        # Verify the mocks were called correctly
        mock_hf_instance.audio_classification.assert_called()
        mock_detect.assert_called_with(text)
        mock_client_instance.tts.assert_called()

if __name__ == '__main__':
    unittest.main() 