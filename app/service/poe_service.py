import logging
import fastapi_poe as fp
from app.config import POE_API_KEY

logger = logging.getLogger(__name__)

async def get_poe_response(message_text: str) -> str:
    logger.info("Getting Poe response for message")
    message = fp.ProtocolMessage(role="user", content=message_text)
    response_parts = []
    async for partial in fp.get_bot_response(
        messages=[message], bot_name="cartagena-trnsl8", api_key=POE_API_KEY
    ):
        if isinstance(partial, str):
            response_parts.append(partial)
        elif hasattr(partial, "text"):
            response_parts.append(partial.text)

    final_response = "".join(response_parts)
    logger.info(f"Got Poe response: {final_response[:100]}...")
    return final_response 