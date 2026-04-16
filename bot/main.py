"""
Entrypoint principal: sobe o bot do Telegram e o servidor web em paralelo.
"""
import asyncio
import threading
import logging
import os
import uvicorn

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


def run_web():
    """Rodar o servidor FastAPI em uma thread separada."""
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=port,
        log_level="warning"
    )


def main():
    # Iniciar servidor web em background
    web_thread = threading.Thread(target=run_web, daemon=True)
    web_thread.start()
    logger.info(f"Servidor web iniciado na porta {os.environ.get('PORT', 8000)}")

    # Iniciar bot
    from bot import main as bot_main
    logger.info("Iniciando bot do Telegram...")
    bot_main()


if __name__ == "__main__":
    main()
