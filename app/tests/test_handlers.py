import unittest
from unittest.mock import Mock, patch
from app.bot.handlers import YourHandlerClass  # Adjust class name and import path

class TestHandlers(unittest.TestCase):
    def setUp(self):
        self.handler = YourHandlerClass()
    
    @patch('app.bot.handlers.PHT')
    @patch('app.bot.handlers.AudioTranscription')
    def test_message_handler(self, mock_transcription, mock_pht):
        # Mock the necessary dependencies
        mock_message = Mock()
        mock_message.voice = Mock()
        mock_message.voice.file_id = "123"
        
        # Mock the bot's get_file method
        mock_bot = Mock()
        mock_bot.get_file.return_value = Mock(file_path="path/to/file")
        mock_bot.download_file.return_value = b'fake_audio_data'
        
        # Test the handler
        result = self.handler.handle_voice_message(mock_message)
        
        # Add assertions based on your handler's expected behavior
        self.assertTrue(mock_transcription.called)
        self.assertTrue(mock_pht.called) 