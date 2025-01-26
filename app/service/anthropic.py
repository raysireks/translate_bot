import logging
from app.config import ANTHROPIC_API_KEY
from anthropic.types import TextBlock, Message
from anthropic import Anthropic
from app.service.prompts.prompts import PROMPTS
import asyncio

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AnthropicService:
    def __init__(self, 
                 locale: str = "cartagena, Colombia",  # Default to cartagena Spanish
                 language: str = "spanish",  # Default language
                 conversation_type: str = "romantic",  # Default conversation type
                 user_gender: str = "male",  # Default user gender
                 recipient_gender: str = "female"):  # Default recipient gender
        self.client = Anthropic(api_key=ANTHROPIC_API_KEY)  # Initialize the Anthropic client
        self.locale = locale
        self.language = language
        self.conversation_type = conversation_type
        self.user_gender = user_gender
        self.recipient_gender = recipient_gender

    async def get_response(self, prompt_key: str = "translate", user_input: str = "") -> str:
        system_prompt = PROMPTS.get(prompt_key, "").format(
            locale=self.locale,
            language=self.language,
            conversation_type=self.conversation_type,
            user_gender=self.user_gender,
            recipient_gender=self.recipient_gender
        )  # Format the prompt with the instance variables
        
        if not system_prompt or not user_input:
            logger.error(f"missing system prompt: {prompt_key} or user input: {user_input}")
            return ""

        try:
            # Run the API call in a thread pool since it's blocking
            result: Message = await asyncio.to_thread(
                self.client.messages.create,
                max_tokens=150,
                model="claude-3-5-sonnet-20240620",
                system=system_prompt,
                temperature=0.2,
                messages=[
                    {
                        "role": "user",
                        "content": user_input
                    }
                ]
            )
            content: list[TextBlock] = result.content
            return content[0].text
        except Exception as e:
            logger.error(f"Error getting response from Anthropics API: {str(e)}")
            return ""

