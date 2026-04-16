import os
import asyncio
import logging
import hashlib
import json
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes, CallbackQueryHandler
)
from database import Database

import cloudinary
import cloudinary.uploader

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

logger = logging.getLogger(__name__)

# =========================
# ENV VARS
# =========================
BOT_TOKEN = os.environ["BOT_TOKEN"]
CHANNEL_ID = os.environ["CHANNEL_ID"]
ADMIN_IDS = [int(x) for x in os.environ.get("ADMIN_IDS", "").split(",") if x]
BASE_URL = os.environ["BASE_URL"]
BOT_USERNAME = os.environ.get("BOT_USERNAME")

# =========================
# CLOUDINARY CONFIG
# =========================
cloudinary.config(
    cloud_name=os.environ["CLOUDINARY_CLOUD_NAME"],
    api_key=os.environ["CLOUDINARY_API_KEY"],
    api_secret=os.environ["CLOUDINARY_API_SECRET"]
)

db = Database()


# =========================
# HELPERS
# =========================
def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def generate_video_id(file_id: str) -> str:
    return hashlib.md5(
        f"{file_id}{datetime.now().isoformat()}".encode()
    ).hexdigest()[:12]


def upload_to_cloudinary(file_path: str) -> str:
    result = cloudinary.uploader.upload(
        file_path,
        resource_type="video"
    )
    return result["secure_url"]


# =========================
# START
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("❌ Acesso negado.")
        return

    await update.message.reply_text(
        f"👋 Olá, {user.first_name}!\n\n"
        "🎬 Bot de vídeos ativo com Cloudinary\n\n"
        "Envie um vídeo para gerar link de player."
    )


# =========================
# HANDLE VIDEO
# =========================
async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("❌ Acesso negado.")
        return

    message = update.message
    video = message.video or message.document

    if not video:
        await message.reply_text("❌ Envie um vídeo válido.")
        return

    processing_msg = await message.reply_text("⏳ Processando vídeo...")

    try:
        # Forward para canal (continua usando Telegram)
        forwarded = await context.bot.forward_message(
            chat_id=CHANNEL_ID,
            from_chat_id=message.chat_id,
            message_id=message.message_id
        )

        file_id = video.file_id
        video_id = generate_video_id(file_id)

        title = message.caption or getattr(video, "file_name", None) or f"Video_{video_id}"
        title = title.strip()

        # =========================
        # DOWNLOAD DO TELEGRAM
        # =========================
        file = await context.bot.get_file(file_id)

        local_path = f"/tmp/{video_id}.mp4"
        await file.download_to_drive(local_path)

        # =========================
        # UPLOAD CLOUDINARY
        # =========================
        video_url = upload_to_cloudinary(local_path)

        # =========================
        # TELEGRAM LINK
        # =========================
        channel_id_str = str(CHANNEL_ID)

        if channel_id_str.startswith("-100"):
            channel_numeric = channel_id_str[4:]
        elif channel_id_str.startswith("-"):
            channel_numeric = channel_id_str[1:]
        else:
            channel_numeric = channel_id_str

        telegram_link = f"https://t.me/c/{channel_numeric}/{forwarded.message_id}"
        player_url = f"{BASE_URL}/player/{video_id}"

        # =========================
        # SAVE DB
        # =========================
        await db.save_video(
            video_id=video_id,
            title=title,
            file_id=file_id,
            telegram_message_id=forwarded.message_id,
            telegram_channel_id=CHANNEL_ID,
            telegram_link=telegram_link,
            player_url=player_url,
            video_url=video_url,
            file_size=video.file_size,
            duration=getattr(video, 'duration', None),
            uploaded_by=user.id
        )

        await processing_msg.edit_text(
            f"✅ Vídeo publicado!\n\n"
            f"🎬 {title}\n"
            f"🔗 Player: {player_url}\n",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🎬 Abrir Player", url=player_url)]
            ])
        )

    except Exception as e:
        logger.error(f"Erro: {e}")
        await processing_msg.edit_text(f"❌ Erro:\n{e}")


# =========================
# LIST VIDEOS
# =========================
async def list_videos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    videos = await db.get_all_videos()

    if not videos:
        await update.message.reply_text("📭 Nenhum vídeo.")
        return

    text = f"🎬 {len(videos)} vídeos:\n\n"

    for v in videos[:20]:
        text += f"• {v['title']}\n{v['player_url']}\n\n"

    await update.message.reply_text(text)


# =========================
# CALLBACK
# =========================
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data.startswith("copy_"):
        video_id = query.data[5:]
        video = await db.get_video(video_id)
        if video:
            await query.message.reply_text(video["player_url"])


# =========================
# MAIN
# =========================
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("list", list_videos))

    app.add_handler(MessageHandler(filters.VIDEO, handle_video))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_video))

    app.add_handler(CallbackQueryHandler(callback_handler))

    logger.info("Bot iniciado com Cloudinary!")
    app.run_polling()


if __name__ == "__main__":
    main()
