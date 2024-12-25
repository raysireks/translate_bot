import unittest
from unittest.mock import patch
from app.service.anthropic import AnthropicService
from app.service.prompts.prompts import PROMPTS

class TestAnthropicService(unittest.TestCase):
    
    @patch('app.service.anthropic.Anthropic')
    def test_get_response_valid_prompt(self, MockAnthropic):
        # Arrange
        mock_client = MockAnthropic.return_value
        mock_client.completions.create.return_value = {"completion": "Translated text"}
        
        service = AnthropicService()
        
        # Act
        response = service.get_response("translate")
        
        # Assert
        self.assertEqual(response, "Translated text")
        mock_client.completions.create.assert_called_once()

    @patch('app.service.anthropic.Anthropic')
    def test_get_response_invalid_prompt(self, MockAnthropic):
        # Arrange
        service = AnthropicService()
        
        # Act
        response = service.get_response("invalid_key")
        
        # Assert
        self.assertEqual(response, "")
        MockAnthropic.assert_not_called()  # Ensure the API was not called

    @patch('app.service.anthropic.Anthropic')
    @patch('app.service.anthropic.logger')
    def test_get_response_api_failure(self, mock_logger, MockAnthropic):
        # Arrange
        mock_client = MockAnthropic.return_value
        mock_client.completions.create.side_effect = Exception("API failure")
        
        service = AnthropicService()
        
        # Act
        response = service.get_response("translate")
        
        # Assert
        self.assertEqual(response, "")
        mock_logger.error.assert_called_once_with("Error getting response from Anthropics API: API failure")

if __name__ == '__main__':
    unittest.main() 