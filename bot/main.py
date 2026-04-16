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
# ✅ CORREÇÃO: __name__ em vez de name
logger = logging.getLogger(__name__)


def run_web():
    """Rodar o servidor FastAPI em uma thread separada."""
    port = int(os.environ.get("PORT", 8000))

    config = uvicorn.Config(
        "server:app",
        host="0.0.0.0",
        port=port,
        log_level="warning",
        loop="asyncio"
    )

    server = uvicorn.Server(config)
    asyncio.run(server.serve())



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


# ✅ CORREÇÃO: __name__ em vez de name
if __name__ == "__main__":
    main()
