@app.get("/player/{video_id}", response_class=HTMLResponse)
async def player_page(video_id: str, request: Request):
    video = await get_video(video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Vídeo não encontrado")

    await increment_views(video_id)

    title = video["title"]
    telegram_link = video.get("telegram_link", "#")

    html = f"""
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{title}</title>

        <style>
            body {{
                margin:0;
                background:#0a0a0f;
                color:white;
                font-family:sans-serif;
                display:flex;
                justify-content:center;
                align-items:center;
                min-height:100vh;
            }}

            .container {{
                width:100%;
                max-width:900px;
                padding:20px;
            }}

            .box {{
                background:#1c1c27;
                border-radius:12px;
                padding:20px;
                text-align:center;
            }}

            .title {{
                font-size:20px;
                margin-bottom:15px;
            }}

            .btn {{
                display:inline-block;
                padding:12px 18px;
                background:#229ED9;
                color:white;
                text-decoration:none;
                border-radius:8px;
                font-weight:bold;
                margin-top:15px;
            }}

            iframe {{
                width:100%;
                height:500px;
                border:none;
                border-radius:12px;
                background:black;
            }}
        </style>
    </head>

    <body>

        <div class="container">

            <div class="box">

                <div class="title">{title}</div>

                <!-- PLAYER FALLBACK -->
                <iframe src="{telegram_link}" allowfullscreen></iframe>

                <br>

                <a class="btn" href="{telegram_link}" target="_blank">
                    Abrir no Telegram
                </a>

            </div>

        </div>

    </body>
    </html>
    """

    return HTMLResponse(content=html)
