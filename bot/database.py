import os
import asyncpg
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

DATABASE_URL = os.environ.get("DATABASE_URL")


class Database:
    def __init__(self):
        self.pool = None

    async def connect(self):
        if not DATABASE_URL:
            logger.warning("DATABASE_URL não definida - banco desativado")
            return

        if not self.pool:
            self.pool = await asyncpg.create_pool(DATABASE_URL)
            await self.create_tables()

    async def create_tables(self):
        async with self.pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS videos (
                    id SERIAL PRIMARY KEY,
                    video_id VARCHAR(20) UNIQUE NOT NULL,
                    title TEXT NOT NULL,

                    -- agora serve para Cloudinary OU fallback Telegram
                    file_id TEXT,
                    video_url TEXT,

                    telegram_message_id BIGINT,
                    telegram_channel_id BIGINT,
                    telegram_link TEXT,

                    player_url TEXT,
                    file_size BIGINT,
                    duration INTEGER,
                    uploaded_by BIGINT,
                    is_online BOOLEAN DEFAULT TRUE,
                    view_count INTEGER DEFAULT 0,
                    last_checked TIMESTAMP,
                    created_at TIMESTAMP DEFAULT NOW()
                );

                CREATE TABLE IF NOT EXISTS config (
                    key VARCHAR(100) PRIMARY KEY,
                    value TEXT,
                    updated_at TIMESTAMP DEFAULT NOW()
                );
            """)

    async def _ensure_connected(self):
        if not DATABASE_URL:
            return
        if not self.pool:
            await self.connect()

    # =========================
    # SAVE VIDEO (CLOUDINARY READY)
    # =========================
    async def save_video(
        self,
        video_id: str,
        title: str,
        file_id: str,
        telegram_message_id: int,
        telegram_channel_id,
        telegram_link: str,
        player_url: str,
        file_size: Optional[int],
        duration: Optional[int],
        uploaded_by: int,
        video_url: Optional[str] = None
    ):
        await self._ensure_connected()
        if not self.pool:
            return

        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO videos (
                    video_id, title, file_id, video_url,
                    telegram_message_id, telegram_channel_id,
                    telegram_link, player_url,
                    file_size, duration, uploaded_by
                )
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)

                ON CONFLICT (video_id) DO UPDATE SET
                    title = EXCLUDED.title,
                    player_url = EXCLUDED.player_url,
                    telegram_link = EXCLUDED.telegram_link,
                    video_url = EXCLUDED.video_url
            """,
            video_id,
            title,
            file_id,
            video_url,
            telegram_message_id,
            int(telegram_channel_id) if telegram_channel_id else None,
            telegram_link,
            player_url,
            file_size,
            duration,
            uploaded_by
            )

    # =========================
    # GET VIDEO
    # =========================
    async def get_video(self, video_id: str) -> Optional[Dict]:
        await self._ensure_connected()
        if not self.pool:
            return None

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM videos WHERE video_id = $1",
                video_id
            )
            return dict(row) if row else None

    async def increment_views(self, video_id: str):
        await self._ensure_connected()
        if not self.pool:
            return

        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE videos SET view_count = view_count + 1 WHERE video_id = $1",
                video_id
            )

    async def get_all_videos(self) -> List[Dict]:
        await self._ensure_connected()
        if not self.pool:
            return []

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM videos ORDER BY created_at DESC"
            )
            return [dict(r) for r in rows]

    async def count_videos(self) -> int:
        await self._ensure_connected()
        if not self.pool:
            return 0

        async with self.pool.acquire() as conn:
            return await conn.fetchval("SELECT COUNT(*) FROM videos")

    async def delete_video(self, video_id: str) -> bool:
        await self._ensure_connected()
        if not self.pool:
            return False

        async with self.pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM videos WHERE video_id = $1",
                video_id
            )
            return result == "DELETE 1"

    async def get_stats(self) -> Dict:
        await self._ensure_connected()
        if not self.pool:
            return {
                "total": 0,
                "online": 0,
                "offline": 0,
                "total_views": 0,
                "last_upload": None
            }

        async with self.pool.acquire() as conn:
            total = await conn.fetchval("SELECT COUNT(*) FROM videos")
            online = await conn.fetchval("SELECT COUNT(*) FROM videos WHERE is_online = TRUE")
            offline = await conn.fetchval("SELECT COUNT(*) FROM videos WHERE is_online = FALSE")
            total_views = await conn.fetchval("SELECT COALESCE(SUM(view_count), 0) FROM videos")
            last_upload = await conn.fetchval("SELECT MAX(created_at) FROM videos")

            return {
                "total": total,
                "online": online,
                "offline": offline,
                "total_views": total_views,
                "last_upload": last_upload.strftime("%d/%m/%Y %H:%M") if last_upload else None
            }

    async def export_backup(self) -> Dict:
        await self._ensure_connected()
        if not self.pool:
            return {"videos": [], "config": []}

        async with self.pool.acquire() as conn:
            videos = await conn.fetch("SELECT * FROM videos ORDER BY created_at")
            configs = await conn.fetch("SELECT * FROM config")

            return {
                "version": "1.0",
                "exported_at": datetime.now().isoformat(),
                "videos": [dict(r) for r in videos],
                "config": [dict(r) for r in configs]
            }
