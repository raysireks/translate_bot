import os
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from app.config import BOT_TOKEN, WEBHOOK_URL, WEBHOOK_PATH, RUN_MODE
from app.bot.handlers import (
    set_transcription_mode,
    set_translation_mode,
    set_voice_type,
    show_commands,
    start,
    handle_message,
    t_command,
    get_chat_id,
    handle_voice,
    toggle_detection,
    toggle_reply,
)
from fastapi import FastAPI, Request
import uvicorn
import asyncio
import logging
import pickle
from pathlib import Path
from types import MappingProxyType

from app.service.audio_transcription import TranscriptionMode

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


async def create_application():
    logger.info("Creating application")
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("t", t_command))
    app.add_handler(CommandHandler("getchatid", get_chat_id))
    app.add_handler(CommandHandler("translation", set_translation_mode))
    app.add_handler(CommandHandler("transcription", set_transcription_mode))
    app.add_handler(CommandHandler("detect", toggle_detection))
    app.add_handler(CommandHandler("reply", toggle_reply))
    app.add_handler(CommandHandler("voice", set_voice_type))
    app.add_handler(CommandHandler("help", show_commands))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))

    logger.info("Handlers added")
    return app


fastapi_app = FastAPI()
telegram_app = None


@fastapi_app.on_event("startup")
async def startup():
    global telegram_app
    logger.info("Starting up application")
    telegram_app = await create_application()

    data_path = Path("/mnt/data_bucket/context.pickle")
    if data_path.exists():
        logger.info("Loading from /mnt/data_bucket/context.pickle")
        try:
            with open(data_path, 'rb') as f:
                loaded_data: dict = pickle.load(f)
            transcription_mode = os.getenv('TRANSCRIPTION_MODE')
            logger.info(f"Transcription mode from env: {transcription_mode}")
            loaded_data.update(transcription_mode=transcription_mode)
            telegram_app.bot_data = MappingProxyType(dict(loaded_data))
        except Exception as e:
            logger.error("Failed to load bot data: %s", e)

    await telegram_app.initialize()
    if RUN_MODE == "webhook":
        await telegram_app.bot.set_webhook(WEBHOOK_URL)


@fastapi_app.post(WEBHOOK_PATH)
async def webhook_handler(request: Request):
    if telegram_app is None:
        logger.error("Telegram app not initialized")
        return {"error": "Application not initialized"}

    update_data = await request.json()
    logger.info(f"Received update data: {update_data}")
    
    # Create background task for processing
    update = Update.de_json(update_data, telegram_app.bot)
    background_task = asyncio.create_task(process_update(update))
    
    # Add error handling for the background task
    background_task.add_done_callback(lambda t: handle_background_task_result(t))
    
    return {"ok": True}

async def process_update(update: Update):
    """Process the update in the background"""
    try:
        logger.info(f"Processing Update object in background: {update}")
        await telegram_app.process_update(update)
        logger.info("Successfully processed update in background")
    except Exception as e:
        logger.error(f"Error processing update in background: {e}", exc_info=True)
        raise

def handle_background_task_result(task):
    """Handle any errors from the background task"""
    try:
        task.result()
    except Exception as e:
        logger.error(f"Background task failed: {e}", exc_info=True)


@fastapi_app.get("/")
async def health_check():
    return {"status": "ok"}


if __name__ == "__main__":
    if RUN_MODE == "webhook":
        uvicorn.run(fastapi_app, host="0.0.0.0", port=8080)
    else:
        asyncio.run(create_application().run_polling())
