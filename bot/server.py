import os
import logging
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import asyncpg
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

# =========================
# ENV VARS (CORRIGIDO)
# =========================
DATABASE_URL = os.environ.get("DATABASE_URL")
BASE_URL = os.environ.get("BASE_URL", "")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL não definida")

pool = None


# =========================
# LIFESPAN (ROBUSTO)
# =========================
@asynccontextmanager
async def lifespan(app: FastAPI):
    global pool
    try:
        pool = await asyncpg.create_pool(DATABASE_URL)
        logger.info("Banco conectado com sucesso")
    except Exception as e:
        logger.error(f"Falha ao conectar no banco: {e}")
        pool = None

    yield

    if pool:
        await pool.close()


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================
# HELPERS
# =========================
async def get_video(video_id: str):
    if not pool:
        raise HTTPException(status_code=500, detail="Banco não conectado")

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM videos WHERE video_id = $1",
            video_id
        )
        return dict(row) if row else None


async def increment_views(video_id: str):
    if not pool:
        return

    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE videos SET view_count = view_count + 1 WHERE video_id = $1",
            video_id
        )


# =========================
# ROUTES
# =========================
@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/")
async def root():
    return HTMLResponse("""
    <html><head><title>Video Bot</title></head>
    <body style="background:#0a0a0f;color:#e8e8f0;font-family:sans-serif;
    display:flex;align-items:center;justify-content:center;height:100vh;margin:0">
    <div style="text-align:center">
    <div style="font-size:48px">🎬</div>
    <h1 style="margin:12px 0 8px">Video Bot</h1>
    <p style="color:#7c7c9a">Player de vídeos via Telegram</p>
    </div></body></html>
    """)


@app.get("/player/{video_id}", response_class=HTMLResponse)
async def player_page(video_id: str, request: Request):
    video = await get_video(video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Vídeo não encontrado")

    await increment_views(video_id)

    channel_id = str(video["telegram_channel_id"])
    if channel_id.startswith("-100"):
        channel_numeric = channel_id[4:]
    elif channel_id.startswith("-"):
        channel_numeric = channel_id[1:]
    else:
        channel_numeric = channel_id

    msg_id = video["telegram_message_id"]
    title = video["title"]

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<meta property="og:title" content="{title}" />
<meta property="og:type" content="video" />
</head>

<body style="background:#0a0a0f;color:white;font-family:sans-serif;">
<h1>{title}</h1>

<script async src="https://telegram.org/js/telegram-widget.js?22"
    data-telegram-post="c/{channel_numeric}/{msg_id}"
    data-width="100%">
</script>

<p>ID: {video_id}</p>
</body>
</html>
"""

    return HTMLResponse(content=html)


@app.get("/api/video/{video_id}")
async def get_video_api(video_id: str):
    video = await get_video(video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Vídeo não encontrado")

    return {
        "video_id": video["video_id"],
        "title": video["title"],
        "player_url": video["player_url"],
        "telegram_link": video["telegram_link"],
        "is_online": video["is_online"],
        "view_count": video["view_count"],
        "created_at": str(video["created_at"])
    }
