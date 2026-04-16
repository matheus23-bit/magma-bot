import os
import logging
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import asyncpg
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

DATABASE_URL = os.environ["DATABASE_URL"]
BASE_URL = os.environ["BASE_URL"]

pool = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global pool
    pool = await asyncpg.create_pool(DATABASE_URL)
    yield
    await pool.close()


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


async def get_video(video_id: str):
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM videos WHERE video_id = $1", video_id)
        return dict(row) if row else None


async def increment_views(video_id: str):
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE videos SET view_count = view_count + 1 WHERE video_id = $1",
            video_id
        )


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

    # HTML do player com o widget embed do Telegram
    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <meta property="og:title" content="{title}" />
    <meta property="og:type" content="video" />
    <meta name="twitter:card" content="player" />
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&display=swap" rel="stylesheet">
    <style>
        *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

        :root {{
            --bg: #0a0a0f;
            --surface: #13131a;
            --surface2: #1c1c27;
            --accent: #6c63ff;
            --accent2: #ff6584;
            --text: #e8e8f0;
            --text-muted: #7c7c9a;
            --border: rgba(108, 99, 255, 0.2);
            --glow: rgba(108, 99, 255, 0.15);
        }}

        html, body {{
            height: 100%;
            background: var(--bg);
            color: var(--text);
            font-family: 'Outfit', sans-serif;
            overflow-x: hidden;
        }}

        body {{
            display: flex;
            flex-direction: column;
            min-height: 100vh;
        }}

        /* Animated background */
        body::before {{
            content: '';
            position: fixed;
            top: -50%;
            left: -50%;
            width: 200%;
            height: 200%;
            background: radial-gradient(ellipse at 30% 20%, rgba(108,99,255,0.08) 0%, transparent 50%),
                        radial-gradient(ellipse at 70% 80%, rgba(255,101,132,0.05) 0%, transparent 50%);
            pointer-events: none;
            z-index: 0;
        }}

        .container {{
            position: relative;
            z-index: 1;
            width: 100%;
            max-width: 960px;
            margin: 0 auto;
            padding: 24px 20px 40px;
            flex: 1;
            display: flex;
            flex-direction: column;
        }}

        /* Header */
        .header {{
            display: flex;
            align-items: center;
            gap: 12px;
            margin-bottom: 28px;
            padding-bottom: 20px;
            border-bottom: 1px solid var(--border);
        }}

        .logo {{
            width: 38px;
            height: 38px;
            background: linear-gradient(135deg, var(--accent), var(--accent2));
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 18px;
            flex-shrink: 0;
            box-shadow: 0 0 20px var(--glow);
        }}

        .header-text h1 {{
            font-size: 13px;
            font-weight: 400;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.1em;
        }}

        /* Video title */
        .video-title {{
            font-size: clamp(18px, 3vw, 26px);
            font-weight: 700;
            line-height: 1.3;
            margin-bottom: 20px;
            background: linear-gradient(135deg, var(--text) 60%, var(--accent));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }}

        /* Player wrapper */
        .player-wrapper {{
            position: relative;
            width: 100%;
            background: var(--surface);
            border-radius: 16px;
            overflow: hidden;
            border: 1px solid var(--border);
            box-shadow: 0 8px 40px rgba(0,0,0,0.5), 0 0 0 1px rgba(255,255,255,0.03);
            margin-bottom: 20px;
        }}

        /* Telegram embed container */
        .tg-embed-container {{
            width: 100%;
            min-height: 420px;
            display: flex;
            align-items: center;
            justify-content: center;
        }}

        .tg-embed-container iframe {{
            width: 100% !important;
            min-height: 420px;
            border: none;
        }}

        /* Fallback player */
        .video-player {{
            width: 100%;
            max-height: 540px;
            display: block;
            background: #000;
        }}

        /* Info bar */
        .info-bar {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            flex-wrap: wrap;
            gap: 12px;
            padding: 16px 20px;
            background: var(--surface2);
            border-radius: 12px;
            border: 1px solid var(--border);
            margin-bottom: 16px;
        }}

        .info-item {{
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 13px;
            color: var(--text-muted);
        }}

        .info-item span.val {{
            color: var(--text);
            font-weight: 500;
        }}

        .badge {{
            display: inline-flex;
            align-items: center;
            gap: 5px;
            padding: 4px 10px;
            border-radius: 20px;
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}

        .badge-online {{
            background: rgba(52, 211, 153, 0.1);
            color: #34d399;
            border: 1px solid rgba(52, 211, 153, 0.2);
        }}

        .badge-offline {{
            background: rgba(239, 68, 68, 0.1);
            color: #ef4444;
            border: 1px solid rgba(239, 68, 68, 0.2);
        }}

        /* Link section */
        .link-box {{
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 12px 16px;
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 10px;
            margin-bottom: 12px;
        }}

        .link-box .link-label {{
            font-size: 11px;
            color: var(--text-muted);
            white-space: nowrap;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.08em;
        }}

        .link-box .link-url {{
            flex: 1;
            font-size: 12px;
            color: var(--accent);
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            font-family: 'Courier New', monospace;
        }}

        .copy-btn {{
            background: var(--accent);
            color: white;
            border: none;
            padding: 6px 14px;
            border-radius: 6px;
            font-size: 12px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
            white-space: nowrap;
        }}

        .copy-btn:hover {{ opacity: 0.85; transform: translateY(-1px); }}
        .copy-btn.copied {{ background: #34d399; }}

        /* Open in Telegram button */
        .tg-btn {{
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 12px 22px;
            background: linear-gradient(135deg, #229ED9, #1a7bbf);
            color: white;
            text-decoration: none;
            border-radius: 10px;
            font-weight: 600;
            font-size: 14px;
            transition: all 0.2s;
            box-shadow: 0 4px 15px rgba(34,158,217,0.3);
        }}

        .tg-btn:hover {{ transform: translateY(-2px); box-shadow: 0 6px 20px rgba(34,158,217,0.4); }}

        .actions {{
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
            margin-top: 8px;
        }}

        /* Footer */
        footer {{
            text-align: center;
            padding: 20px;
            font-size: 12px;
            color: var(--text-muted);
            border-top: 1px solid var(--border);
            z-index: 1;
            position: relative;
        }}

        @media (max-width: 600px) {{
            .info-bar {{ flex-direction: column; align-items: flex-start; }}
            .tg-embed-container {{ min-height: 280px; }}
            .tg-embed-container iframe {{ min-height: 280px; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="logo">🎬</div>
            <div class="header-text">
                <h1>Video Player</h1>
            </div>
        </div>

        <div class="video-title">{title}</div>

        <div class="player-wrapper">
            <div class="tg-embed-container" id="playerContainer">
                <!-- Telegram embed widget -->
                <script async src="https://telegram.org/js/telegram-widget.js?22"
                    data-telegram-post="c/{channel_numeric}/{msg_id}"
                    data-width="100%"
                    data-userpic="false"
                    data-color="6C63FF"
                    data-dark-color="6C63FF"
                    data-dark="1">
                </script>
            </div>
        </div>

        <div class="info-bar">
            <div class="info-item">
                <span>🆔</span>
                <span class="val">{video_id}</span>
            </div>
            <div class="info-item">
                <span>👁️</span>
                <span class="val" id="viewCount">{video.get("view_count", 0)} views</span>
            </div>
            <span class="badge badge-online">● Online</span>
        </div>

        <div class="link-box">
            <span class="link-label">🔗 Link</span>
            <span class="link-url" id="playerUrl">{BASE_URL}/player/{video_id}</span>
            <button class="copy-btn" onclick="copyLink('playerUrl', this)">Copiar</button>
        </div>

        <div class="actions">
            <a href="{video.get("telegram_link", "#")}" target="_blank" class="tg-btn">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="white">
                    <path d="M12 0C5.373 0 0 5.373 0 12s5.373 12 12 12 12-5.373 12-12S18.627 0 12 0zm5.894 8.221l-1.97 9.28c-.145.658-.537.818-1.084.508l-3-2.21-1.447 1.394c-.16.16-.295.295-.605.295l.213-3.053 5.56-5.023c.242-.213-.054-.333-.373-.12l-6.871 4.326-2.962-.924c-.643-.204-.657-.643.136-.953l11.57-4.461c.537-.194 1.006.131.833.941z"/>
                </svg>
                Abrir no Telegram
            </a>
        </div>
    </div>

    <footer>
        Powered by Telegram Video Bot &bull; {video_id}
    </footer>

    <script>
        function copyLink(elementId, btn) {{
            const text = document.getElementById(elementId).textContent;
            navigator.clipboard.writeText(text).then(() => {{
                btn.textContent = '✓ Copiado!';
                btn.classList.add('copied');
                setTimeout(() => {{
                    btn.textContent = 'Copiar';
                    btn.classList.remove('copied');
                }}, 2000);
            }});
        }}
    </script>
</body>
</html>"""

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
