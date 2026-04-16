import os
import asyncio
import logging
import hashlib
import cloudinary
import cloudinary.uploader
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes, CallbackQueryHandler
)
from database import Database

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

logger = logging.getLogger(__name__)

# ======================
# ENV
# ======================
BOT_TOKEN = os.environ["BOT_TOKEN"]
CHANNEL_ID = os.environ["CHANNEL_ID"]
ADMIN_IDS = [int(x) for x in os.environ.get("ADMIN_IDS", "").split(",") if x]
BASE_URL = os.environ["BASE_URL"]

CLOUD_NAME = os.environ["CLOUDINARY_CLOUD_NAME"]
CLOUD_API_KEY = os.environ["CLOUDINARY_API_KEY"]
CLOUD_API_SECRET = os.environ["CLOUDINARY_API_SECRET"]

# ======================
# CLOUDINARY CONFIG
# ======================
cloudinary.config(
    cloud_name=CLOUD_NAME,
    api_key=CLOUD_API_KEY,
    api_secret=CLOUD_API_SECRET,
    secure=True
)

db = Database()


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def generate_video_id(file_id: str) -> str:
    return hashlib.md5(
        f"{file_id}{datetime.now().isoformat()}".encode()
    ).hexdigest()[:12]


# ======================
# UPLOAD CLOUDINARY
# ======================
async def upload_to_cloudinary(file_path: str) -> str:
    loop = asyncio.get_event_loop()

    def upload():
        result = cloudinary.uploader.upload_large(
            file_path,
            resource_type="video"
        )
        return result["secure_url"]

    return await loop.run_in_executor(None, upload)


# ======================
# START
# ======================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("❌ Sem permissão")
        return

    await update.message.reply_text("👋 Bot ativo com Cloudinary!")


# ======================
# VIDEO HANDLER
# ======================
async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        return

    msg = update.message
    video = msg.video or msg.document

    if not video:
        return

    processing = await msg.reply_text("⏳ enviando para Cloudinary...")

    try:
        # 1. baixar arquivo do telegram
        file = await context.bot.get_file(video.file_id)
        file_path = f"/tmp/{video.file_id}.mp4"
        await file.download_to_drive(file_path)

        # 2. upload cloudinary
        cloud_url = await upload_to_cloudinary(file_path)

        video_id = generate_video_id(video.file_id)

        title = msg.caption or f"Video_{video_id}"

        player_url = f"{BASE_URL}/player/{video_id}"

        # 3. salvar no banco
        await db.save_video(
            video_id=video_id,
            title=title,
            file_id=cloud_url,
            telegram_message_id=0,
            telegram_channel_id=0,
            telegram_link=cloud_url,
            player_url=player_url,
            file_size=video.file_size,
            duration=getattr(video, "duration", None),
            uploaded_by=user.id
        )

        await processing.edit_text(
            f"✅ Vídeo salvo no Cloudinary!\n\n"
            f"🎬 {title}\n"
            f"🔗 {player_url}\n"
            f"☁️ {cloud_url}"
        )

    except Exception as e:
        logger.error(e)
        await processing.edit_text(f"❌ erro: {e}")


# ======================
# BOT MAIN
# ======================
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.VIDEO, handle_video))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_video))

    logger.info("Bot rodando com Cloudinary")
    app.run_polling()


if __name__ == "__main__":
    main()
