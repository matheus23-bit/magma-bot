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


# =========================
# WEB SERVER THREAD
# =========================
def run_web():
    """Rodar o servidor FastAPI em uma thread separada."""
    port = int(os.environ.get("PORT", 8000))

    config = uvicorn.Config(
        "server:app",
        host="0.0.0.0",
        port=port,
        log_level="info",
        loop="asyncio"
    )

    server = uvicorn.Server(config)

    # FIX IMPORTANTE: não usar asyncio.run dentro de thread
    asyncio.set_event_loop(asyncio.new_event_loop())
    loop = asyncio.get_event_loop()
    loop.run_until_complete(server.serve())


# =========================
# MAIN
# =========================
def main():
    web_thread = threading.Thread(target=run_web, daemon=True)
    web_thread.start()

    logger.info(f"Servidor web iniciado na porta {os.environ.get('PORT', 8000)}")

    try:
        from bot import main as bot_main
        logger.info("Iniciando bot do Telegram...")
        bot_main()

    except Exception as e:
        logger.error(f"Erro ao iniciar bot: {e}")
        raise


# =========================
# ENTRYPOINT
# =========================
if __name__ == "__main__":
    main()
