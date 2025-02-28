import asyncio
import logging
import os
import pickle
from pathlib import Path
from types import MappingProxyType
import sys

from fastapi import FastAPI, Request, HTTPException
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

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
from app.config import BOT_TOKEN, WEBHOOK_URL, WEBHOOK_PATH, RUN_MODE
from app.service.audio_transcription import TranscriptionMode
from app.api.routes import router as api_router

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", 
    level=logging.INFO
)
logger = logging.getLogger(__name__)

fastapi_app = FastAPI()
telegram_app = None

@fastapi_app.on_event("startup")
async def startup():
    global telegram_app
    logger.info("Starting up application")
    
    # Initialize Telegram app unless in REST mode
    if RUN_MODE != "rest":
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
    else:
        logger.info("Running in REST API mode - Telegram bot disabled")

    # Check if Angular build directory exists
    angular_build_path = Path("./universal-translator/dist/universal-translator")
    if angular_build_path.exists() and angular_build_path.is_dir():
        logger.info(f"Mounting Angular build directory: {angular_build_path}")
        fastapi_app.mount("/", StaticFiles(directory=angular_build_path, html=True), name="angular")
    else:
        logger.warning(f"Angular build directory not found at {angular_build_path}")

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

@fastapi_app.post(WEBHOOK_PATH)
async def webhook_handler(request: Request):
    # If in REST mode, return an appropriate message
    if RUN_MODE == "rest":
        logger.info("Webhook endpoint accessed in REST mode")
        return {"message": "Telegram webhook is disabled in REST API mode"}
        
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

@fastapi_app.get("/{full_path:path}")
async def serve_angular(full_path: str):
    # Skip API routes
    if full_path.startswith("api/") or full_path == WEBHOOK_PATH.lstrip("/"):
        raise HTTPException(status_code=404, detail="Not found")
    
    # For static assets (.js, .css, etc), serve them directly with correct MIME type
    angular_dir = Path("./universal-translator/dist/universal-translator")
    requested_file = angular_dir / full_path
    
    if requested_file.exists() and requested_file.is_file():
        # If the file exists, serve it directly
        if full_path.endswith('.js'):
            return FileResponse(requested_file, media_type="application/javascript")
        elif full_path.endswith('.css'):
            return FileResponse(requested_file, media_type="text/css")
        elif full_path.endswith('.ico'):
            return FileResponse(requested_file, media_type="image/x-icon")
        else:
            # For other file types, let FastAPI guess the MIME type
            return FileResponse(requested_file)
    else:
        logger.warning(f"Angular index.html not found at {requested_file}")
        return {"error": "Frontend not available"}

@fastapi_app.get("/")
async def health_check():
    return {"status": "ok"}

# Add CORS middleware
fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include the API router
fastapi_app.include_router(api_router)

def main():
    try:
        logger.info("Starting application initialization...")
        
        if RUN_MODE == "webhook":
            logger.info("Starting in webhook mode")
            import uvicorn
            uvicorn.run(fastapi_app, host="0.0.0.0", port=8080)
        elif RUN_MODE == "rest":
            logger.info("Starting in REST API mode")
            import uvicorn
            uvicorn.run(fastapi_app, host="0.0.0.0", port=8080)
        else:
            logger.info("Starting in polling mode")
            asyncio.run(create_application().run_polling())
            
    except Exception as e:
        logger.error("Fatal error: %s", e, exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    logger.info("Starting main...")
    main()
