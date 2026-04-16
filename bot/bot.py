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

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHANNEL_ID = os.environ["CHANNEL_ID"]          # Ex: -1001234567890
ADMIN_IDS = [int(x) for x in os.environ.get("ADMIN_IDS", "").split(",") if x]
BASE_URL = os.environ["BASE_URL"]               # Ex: https://seu-app.railway.app
BOT_USERNAME = os.environ.get("BOT_USERNAME")  # Ex: meubot (sem @)

db = Database()


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def generate_video_id(file_id: str) -> str:
    return hashlib.md5(f"{file_id}{datetime.now().isoformat()}".encode()).hexdigest()[:12]


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("❌ Acesso negado. Você não tem permissão para usar este bot.")
        return

    await update.message.reply_text(
        f"👋 Olá, {user.first_name}!\n\n"
        "🎬 *Bot de Player de Vídeos*\n\n"
        "Envie qualquer arquivo de vídeo e vou gerar um link de player para você.\n\n"
        "📋 *Comandos disponíveis:*\n"
        "/start - Menu inicial\n"
        "/list - Listar todos os vídeos\n"
        "/backup - Exportar backup das configurações\n"
        "/restore - Importar backup\n"
        "/check - Verificar links offline\n"
        "/stats - Estatísticas\n"
        "/delete <id> - Deletar um vídeo",
        parse_mode="Markdown"
    )


async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("❌ Acesso negado.")
        return

    message = update.message
    video = message.video or message.document

    if not video:
        await message.reply_text("❌ Por favor, envie um arquivo de vídeo.")
        return

    # Verificar se é vídeo
    if message.document:
        mime = message.document.mime_type or ""
        if not mime.startswith("video/"):
            await message.reply_text("❌ Este arquivo não é um vídeo. Envie um arquivo de vídeo válido.")
            return

    processing_msg = await message.reply_text("⏳ Processando vídeo...")

    try:
        # Fazer forward pro canal privado
        forwarded = await context.bot.forward_message(
            chat_id=CHANNEL_ID,
            from_chat_id=message.chat_id,
            message_id=message.message_id
        )

        # Gerar ID único para o vídeo
        file_id = video.file_id
        video_id = generate_video_id(file_id)

        # Nome do vídeo
        title = message.caption or (
            video.file_name if hasattr(video, 'file_name') and video.file_name else f"Video_{video_id}"
        )
        title = title.strip()

        # Extrair channel_id numérico (sem o -100)
        channel_id_str = str(CHANNEL_ID)
        if channel_id_str.startswith("-100"):
            channel_numeric = channel_id_str[4:]
        elif channel_id_str.startswith("-"):
            channel_numeric = channel_id_str[1:]
        else:
            channel_numeric = channel_id_str

        # Link direto do Telegram para o vídeo no canal
        telegram_link = f"https://t.me/c/{channel_numeric}/{forwarded.message_id}"

        # Link do player web (abre no navegador)
        player_url = f"{BASE_URL}/player/{video_id}"

        # Salvar no banco
        await db.save_video(
            video_id=video_id,
            title=title,
            file_id=file_id,
            telegram_message_id=forwarded.message_id,
            telegram_channel_id=CHANNEL_ID,
            telegram_link=telegram_link,
            player_url=player_url,
            file_size=video.file_size,
            duration=getattr(video, 'duration', None),
            uploaded_by=user.id
        )

        await processing_msg.edit_text(
            f"✅ *Vídeo publicado com sucesso!*\n\n"
            f"🎬 *Título:* {title}\n"
            f"🆔 *ID:* `{video_id}`\n\n"
            f"🔗 *Link do Player:*\n`{player_url}`\n\n"
            f"📱 *Link Telegram:*\n`{telegram_link}`\n\n"
            f"_(O link do player abre no navegador)_",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🎬 Abrir Player", url=player_url)],
                [InlineKeyboardButton("📋 Copiar Link", callback_data=f"copy_{video_id}")]
            ])
        )

    except Exception as e:
        logger.error(f"Erro ao processar vídeo: {e}")
        await processing_msg.edit_text(
            f"❌ Erro ao processar o vídeo:\n`{str(e)}`",
            parse_mode="Markdown"
        )


async def list_videos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    videos = await db.get_all_videos()

    if not videos:
        await update.message.reply_text("📭 Nenhum vídeo cadastrado ainda.")
        return

    text = f"🎬 *{len(videos)} vídeo(s) cadastrado(s):*\n\n"

    for i, v in enumerate(videos[:20], 1):
        status = "✅" if v.get("is_online", True) else "❌"
        text += f"{i}. {status} *{v['title'][:40]}*\n"
        text += f"   🆔 `{v['video_id']}`\n"
        text += f"   🔗 {v['player_url']}\n\n"

    if len(videos) > 20:
        text += f"_... e mais {len(videos) - 20} vídeos_"

    await update.message.reply_text(text, parse_mode="Markdown")


async def backup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    await update.message.reply_text("⏳ Gerando backup...")

    try:
        backup_data = await db.export_backup()
        backup_json = json.dumps(backup_data, indent=2, ensure_ascii=False, default=str)

        # Enviar como arquivo
        from io import BytesIO
        bio = BytesIO(backup_json.encode("utf-8"))
        bio.name = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        await update.message.reply_document(
            document=bio,
            caption=(
                f"✅ *Backup gerado com sucesso!*\n\n"
                f"📊 {len(backup_data.get('videos', []))} vídeo(s)\n"
                f"📅 {datetime.now().strftime('%d/%m/%Y %H:%M')}\n\n"
                f"_Guarde este arquivo com segurança para restaurar o bot em outra conta._"
            ),
            parse_mode="Markdown"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Erro ao gerar backup:\n`{e}`", parse_mode="Markdown")


async def restore_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    await update.message.reply_text(
        "📥 *Restaurar Backup*\n\n"
        "Envie o arquivo JSON de backup como documento.\n"
        "⚠️ Isso irá importar todos os vídeos do backup.",
        parse_mode="Markdown"
    )
    context.user_data["waiting_restore"] = True


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    # Restaurar backup
    if context.user_data.get("waiting_restore"):
        context.user_data["waiting_restore"] = False
        doc = update.message.document

        if not doc.file_name.endswith(".json"):
            await update.message.reply_text("❌ Por favor, envie um arquivo .json")
            return

        processing = await update.message.reply_text("⏳ Importando backup...")

        try:
            file = await context.bot.get_file(doc.file_id)
            content = await file.download_as_bytearray()
            backup_data = json.loads(content.decode("utf-8"))

            count = await db.import_backup(backup_data)

            await processing.edit_text(
                f"✅ *Backup restaurado!*\n\n"
                f"📊 {count} vídeo(s) importado(s)",
                parse_mode="Markdown"
            )
        except Exception as e:
            await processing.edit_text(f"❌ Erro ao restaurar:\n`{e}`", parse_mode="Markdown")
        return

    # Se não é restore, verificar se é vídeo (document com mime video/)
    doc = update.message.document
    if doc and doc.mime_type and doc.mime_type.startswith("video/"):
        await handle_video(update, context)


async def check_links(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    await update.message.reply_text("🔍 Verificando links... pode demorar alguns segundos.")

    offline = await db.get_offline_videos()
    total = await db.count_videos()

    if not offline:
        await update.message.reply_text(
            f"✅ Todos os {total} link(s) estão online!"
        )
    else:
        text = f"⚠️ *{len(offline)} link(s) offline de {total} total:*\n\n"
        for v in offline:
            text += f"❌ *{v['title'][:40]}*\n"
            text += f"   🆔 `{v['video_id']}`\n\n"

        await update.message.reply_text(text, parse_mode="Markdown")


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    stats = await db.get_stats()

    await update.message.reply_text(
        f"📊 *Estatísticas*\n\n"
        f"🎬 Total de vídeos: *{stats['total']}*\n"
        f"✅ Online: *{stats['online']}*\n"
        f"❌ Offline: *{stats['offline']}*\n"
        f"👁️ Total de views: *{stats['total_views']}*\n"
        f"📅 Último upload: *{stats['last_upload'] or 'N/A'}*",
        parse_mode="Markdown"
    )


async def delete_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    if not context.args:
        await update.message.reply_text("Uso: /delete <video_id>")
        return

    video_id = context.args[0]
    success = await db.delete_video(video_id)

    if success:
        await update.message.reply_text(f"✅ Vídeo `{video_id}` deletado.", parse_mode="Markdown")
    else:
        await update.message.reply_text(f"❌ Vídeo `{video_id}` não encontrado.", parse_mode="Markdown")


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data.startswith("copy_"):
        video_id = query.data[5:]
        video = await db.get_video(video_id)
        if video:
            await query.message.reply_text(
                f"🔗 Link do player:\n`{video['player_url']}`",
                parse_mode="Markdown"
            )


async def monitor_links(app: Application):
    """Task periódica para monitorar links offline."""
    while True:
        try:
            await asyncio.sleep(3600)  # Checar a cada 1 hora
            offline = await db.get_offline_videos()

            if offline:
                for admin_id in ADMIN_IDS:
                    text = f"🚨 *Alerta: {len(offline)} link(s) offline!*\n\n"
                    for v in offline[:10]:
                        text += f"❌ *{v['title'][:40]}*\n"
                        text += f"   🆔 `{v['video_id']}`\n"
                        text += f"   🔗 {v['player_url']}\n\n"

                    try:
                        await app.bot.send_message(
                            chat_id=admin_id,
                            text=text,
                            parse_mode="Markdown"
                        )
                    except Exception as e:
                        logger.error(f"Erro ao notificar admin {admin_id}: {e}")
        except Exception as e:
            logger.error(f"Erro no monitor: {e}")


def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("list", list_videos))
    app.add_handler(CommandHandler("backup", backup_command))
    app.add_handler(CommandHandler("restore", restore_command))
    app.add_handler(CommandHandler("check", check_links))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("delete", delete_video))

    app.add_handler(MessageHandler(filters.VIDEO, handle_video))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(CallbackQueryHandler(callback_handler))

    # Iniciar monitor em background
    loop = asyncio.get_event_loop()
    loop.create_task(monitor_links(app))

    logger.info("Bot iniciado!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
