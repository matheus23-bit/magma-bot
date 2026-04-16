@app.get("/player/{video_id}", response_class=HTMLResponse)
async def player_page(video_id: str, request: Request):
    video = await get_video(video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Vídeo não encontrado")

    await increment_views(video_id)

    title = video["title"]
    video_url = video.get("cloudinary_url")  # 🔥 NOVO CAMPO

    if not video_url:
        raise HTTPException(status_code=404, detail="Vídeo sem URL")

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

            video {{
                width:100%;
                border-radius:12px;
                background:black;
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
        </style>
    </head>

    <body>
        <div class="container">
            <div class="box">

                <div class="title">{title}</div>

                <!-- PLAYER REAL (CLOUDINARY / CDN) -->
                <video controls autoplay>
                    <source src="{video_url}" type="video/mp4">
                    Seu navegador não suporta vídeo.
                </video>

                <br>

                <a class="btn" href="{video_url}" target="_blank">
                    Abrir vídeo direto
                </a>

            </div>
        </div>
    </body>
    </html>
    """

    return HTMLResponse(content=html)
