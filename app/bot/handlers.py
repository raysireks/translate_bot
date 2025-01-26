import asyncio
import io
import pickle
import re
from telegram import Update
from telegram.ext import ContextTypes
import emoji
from app.config import ALLOWED_GROUP_ID, ADMIN_USER_ID
import logging
from types import MappingProxyType

from app.service.audio_transcription import TranscriptionMode, WhisperHandler
from app.service.pht import PHT
from app.service.anthropic import AnthropicService

logger = logging.getLogger(__name__)

# Initialize the Anthropic service
anthropic_service = AnthropicService()

def is_emoji_only(text: str) -> bool:
    return all(c in emoji.EMOJI_DATA or c.isspace() for c in text)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Start command from user {update.message.from_user.id}")
    await send_message(update, context, "Hello! I'm ready to translate")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(
        f"Handling message from user {update.message.from_user.id}: {update.message.text[:100]}"
    )
    # Fire and forget the filter and typing indicator
    asyncio.create_task(message_filter(update, context))
    asyncio.create_task(update.message.chat.send_action("typing"))

    if update.message.text.startswith("-"):
        logger.info("Skipping message starting with -")
        return

    if is_emoji_only(update.message.text):
        logger.info("Skipping emoji-only message")
        return

    try:
        response = await anthropic_service.get_response(user_input=update.message.text)
        if response:
            logger.info("Sending response to user")
            asyncio.create_task(send_message(update, context, response))
        else:
            logger.warning("Empty response from Anthropic")
            asyncio.create_task(send_message(update, context, 
                "Sorry, I received an empty response. Please try again."
            ))
    except Exception as e:
        logger.error(f"Error in handle_message: {str(e)}", exc_info=True)
        asyncio.create_task(send_message(update, context, 
            "Sorry, I encountered an error: {}".format(str(e))
        ))

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Handling voice message from user {update.message.from_user.id}")
    try:
        voice = update.message.voice
        if voice:
            # Fire off typing indicator and message filter
            asyncio.create_task(update.message.chat.send_action("typing"))
            asyncio.create_task(message_filter(update, context))

            model_name = context.application.bot_data.get("translation_mode", "base")
            mode = context.application.bot_data.get("transcription_mode", TranscriptionMode.LOCAL.value)
            detect_language = context.application.bot_data.get("translation_detect", False)

            logger.info(f"Using mode: {mode} with model: {model_name}")

            file = await context.bot.get_file(voice.file_id)
            voice_data = await file.download_as_bytearray()
            handler = WhisperHandler(mode, model_name)

            transcribed_text = await handler.transcribe_voice(voice_data, detect_language)
            logger.info(f"Transcribed text: {transcribed_text}")

            asyncio.create_task(update.message.chat.send_action("typing"))
            
            if transcribed_text:
                translation = await anthropic_service.get_response(user_input=transcribed_text)
                asyncio.create_task(message_filter(update, context, translation))
                
                if translation:
                    logger.info("Sending translation to user")
                    asyncio.create_task(
                        send_message(update, context, f"{translation} ({transcribed_text})")
                    )
                    
                    # Generate TTS response
                    tts_response = await generate_tts(voice_data, translation)
                    audio_bytes = bytes(tts_response)     
                    audio_buffer = io.BytesIO(audio_bytes)
                    audio_buffer.name = "audio.mp3" 
                    
                    await context.bot.send_voice(
                        update.message.chat_id, 
                        audio_buffer
                    )
                else:
                    logger.warning("Empty translation from Anthropic")
                    asyncio.create_task(
                        send_message(update, context, "Sorry, couldn't get translation. Original text: " + transcribed_text)
                    )
            else:
                logger.warning("Empty transcription")
                asyncio.create_task(
                    send_message(update, context, "Sorry, couldn't transcribe the audio. Please try again.")
                )

    except Exception as e:
        logger.error(f"Error in handle_voice: {str(e)}", exc_info=True)
        asyncio.create_task(
            send_message(update, context, "Sorry, there was an error processing your voice message.")
        )

# async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     logger.info(f"Handling voice message from user {update.message.from_user.id}")
#     try:
#         voice = update.message.voice
#         if voice:
#             await update.message.chat.send_action("typing")

#             model_name = context.application.bot_data.get("translation_mode", "base")
#             mode = context.application.bot_data.get("transcription_mode", TranscriptionMode.LOCAL.value)
#             detect_language = context.application.bot_data.get("translation_detect", False)

#             logger.info(f"Using mode: {mode} with model: {model_name}")

#             file = await context.bot.get_file(voice.file_id)
#             voice_data = await file.download_as_bytearray()
#             handler = WhisperHandler(mode, model_name)

#             transcribed_text = await handler.transcribe_voice(voice_data, detect_language)
#             logger.info(f"Transcribed text: {transcribed_text}")

#             await update.message.chat.send_action("typing")
#             if transcribed_text:
#                 translation = await get_poe_response(transcribed_text)
#                 await message_filter(update, context, translation)
#                 if translation:
#                     logger.info("Sending translation to user")
#                     await send_message(update, context, f"{translation} ({transcribed_text})")
                    
#                     # Generate TTS response
#                     # tts_response = await handler.cloneAudioTTS(context, translation, voice_data)
#                     tts_response = await generate_tts(translation)
#                     audio_bytes = bytes(tts_response)     

#                     await context.bot.send_voice(
#                         update.message.chat_id, 
#                         audio_bytes
#                     )
#                 else:
#                     logger.warning("Empty translation from Poe")
#                     await send_message(update, context, "Sorry, couldn't get translation. Original text: " + transcribed_text)
#             else:
#                 logger.warning("Empty transcription")
#                 await send_message(update, context, "Sorry, couldn't transcribe the audio. Please try again.")

#     except Exception as e:
#         logger.error(f"Error in handle_voice: {str(e)}", exc_info=True)
#         await send_message(update, context, "Sorry, there was an error processing your voice message.")


async def t_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"T command from user {update.message.from_user.id}")
    await handle_message(update, context)


async def get_chat_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Get chat ID command from user {update.message.from_user.id}")
    await send_message(update, context, 
        "This chat's ID is: {}".format(update.message.chat.id)
    )


async def message_filter(
    update: Update, context: ContextTypes.DEFAULT_TYPE, translation: str = ""
):
    logger.info(f"Filtering message from chat ID: {update.message.chat.id}")

    if (
        update.message.chat.type == "private"
        and update.message.from_user.id != ADMIN_USER_ID
    ) or (
        update.message.chat.type in ["group", "supergroup"]
        and update.message.chat.id != ALLOWED_GROUP_ID
    ):
        user = update.message.from_user
        user_info = []
        if user.username:
            user_info.append("Username: @{}".format(user.username))
        if user.first_name:
            user_info.append("First Name: {}".format(user.first_name))
        if user.last_name:
            user_info.append("Last Name: {}".format(user.last_name))

        notification = "Message from outside:\nGroup: {}\n{}\nMessage: {}".format(
            update.message.chat.title, "\n".join(user_info), update.message.text
        )
        logger.info(f"Sending notification to admin about message from user {user.id}")
        await context.bot.send_message(chat_id=ADMIN_USER_ID, text=notification)
        if update.message.voice:
            await context.bot.send_voice(
                chat_id=ADMIN_USER_ID, voice=update.message.voice.file_id
            )
            await context.bot.send_message(chat_id=ADMIN_USER_ID, text=translation)


async def send_message(update: Update, context: ContextTypes.DEFAULT_TYPE, response: str):
   if context.application.bot_data.get("reply", False):
       await update.message.reply_text(response)
   else:
       await context.bot.send_message(chat_id=update.effective_chat.id, text=response)

async def set_translation_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Set translation mode command from user {update.message.from_user.id}")
    
    if not context.args:
        await send_message(update, context,
            f"Usage: /translation [base|small|large]\n"
            f"Current mode: {context.application.bot_data.get('translation_mode', 'base')}"
        )
        return
        
    mode = context.args[0].lower()
    if mode not in ["base", "small", "large"]:
        await send_message(update, context, "Invalid mode. Use: base/small/large")
        return
        
    current_data = dict(context.application.bot_data)
    current_data["translation_mode"] = mode
    message = f"Translation mode set to: {mode}"
    
    await save_context(update, context, current_data, message)

async def set_transcription_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Set transcription mode command from user {update.message.from_user.id}")
    
    if not context.args:
        await send_message(update, context,
            f"Usage: /transcription [local|hf]\n"
            f"Current mode: {context.application.bot_data.get('transcription_mode', 'local')}"
        )
        return
        
    mode = context.args[0].lower()
    if mode not in ["local", "hf"]:
        await send_message(update, context, "Invalid mode. Use: local/hf")
        return
        
    current_data = dict(context.application.bot_data)
    current_data["transcription_mode"] = mode
    message = f"Transcription mode set to: {mode}"
    
    await save_context(update, context, current_data, message)

async def toggle_detection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Toggle detection command from user {update.message.from_user.id}")
    
    current_data = dict(context.application.bot_data)
    current_data["translation_detect"] = not current_data.get("translation_detect", False)
    status = "enabled" if current_data["translation_detect"] else "disabled"
    message = f"Translation auto-detection {status}"
    
    await save_context(update, context, current_data, message)

async def toggle_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Toggle reply command from user {update.message.from_user.id}")
    
    current_data = dict(context.application.bot_data)
    current_data["reply"] = not current_data.get("reply", False)
    status = "enabled" if current_data["reply"] else "disabled"
    message = f"Reply mode {status}"
    
    await save_context(update, context, current_data, message)

async def set_voice_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Set voice type command from user {update.message.from_user.id}")
    
    if not context.args:
        current_voice = context.application.bot_data.get("voice_type", "en0")
        await send_message(update, context,
            f"Usage: /voice [language code][number] (e.g., en0, es1)\n"
            f"Current voice: {current_voice}"
        )
        return
        
    voice = context.args[0].lower()
    if not re.match(r'^(en|es)[0-9]$', voice):
        await send_message(update, context, "Invalid voice type. Format: (en|es)(0-9)")
        return
        
    current_data = dict(context.application.bot_data)
    current_data["voice_type"] = voice
    message = f"Voice type set to: {voice}"
    
    await save_context(update, context, current_data, message)

async def save_context(update: Update, context: ContextTypes.DEFAULT_TYPE, current_data: dict, message: str):
    logger.info(message)
    context.application.bot_data = MappingProxyType(current_data)
    await send_message(update, context, message)
    
    try:
        with open("/mnt/data_bucket/context.pickle", "wb") as f:
            pickle.dump(current_data, f)
    except Exception as e:
        logger.error("Failed to save pickle: %s", e)

async def show_commands(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Help command from user {update.message.from_user.id}")
    
    current_data = context.application.bot_data
    help_text = """
Available Commands:
/start - Start the bot
/t [text] - Translate text
/translation [base|small|large] - Set translation model
    Current: {translation_mode}
/transcription [local|hf] - Set transcription mode
    Current: {transcription_mode}
/detect - Toggle language auto-detection
    Current: {detect_status}
/reply - Toggle automatic reply mode
    Current: {reply_status}
/voice [lang][num] - Set voice type (e.g., en0, es1)
    Current: {voice_type}
/getchatid - Get current chat ID
/help - Show this help message
""".format(
        translation_mode=current_data.get('translation_mode', 'base'),
        transcription_mode=current_data.get('transcription_mode', 'local'),
        detect_status='enabled' if current_data.get('translation_detect', False) else 'disabled',
        reply_status='enabled' if current_data.get('reply', False) else 'disabled',
        voice_type=current_data.get('voice_type', 'en0')
    )
    
    await send_message(update, context, help_text)