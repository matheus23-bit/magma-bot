import os
import asyncpg
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

DATABASE_URL = os.environ["DATABASE_URL"]


class Database:
    def __init__(self):
        self.pool = None

    async def connect(self):
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
                    file_id TEXT NOT NULL,
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
        if not self.pool:
            await self.connect()

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
        uploaded_by: int
    ):
        await self._ensure_connected()
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO videos (
                    video_id, title, file_id, telegram_message_id, telegram_channel_id,
                    telegram_link, player_url, file_size, duration, uploaded_by
                ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
                ON CONFLICT (video_id) DO UPDATE SET
                    title = EXCLUDED.title,
                    player_url = EXCLUDED.player_url,
                    telegram_link = EXCLUDED.telegram_link
            """,
            video_id, title, file_id, telegram_message_id, int(telegram_channel_id),
            telegram_link, player_url, file_size, duration, uploaded_by
            )

    async def get_video(self, video_id: str) -> Optional[Dict]:
        await self._ensure_connected()
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM videos WHERE video_id = $1", video_id
            )
            return dict(row) if row else None

    async def increment_views(self, video_id: str):
        await self._ensure_connected()
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE videos SET view_count = view_count + 1 WHERE video_id = $1",
                video_id
            )

    async def get_all_videos(self) -> List[Dict]:
        await self._ensure_connected()
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM videos ORDER BY created_at DESC"
            )
            return [dict(r) for r in rows]

    async def get_offline_videos(self) -> List[Dict]:
        await self._ensure_connected()
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM videos WHERE is_online = FALSE ORDER BY created_at DESC"
            )
            return [dict(r) for r in rows]

    async def set_video_status(self, video_id: str, is_online: bool):
        await self._ensure_connected()
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE videos SET is_online = $1, last_checked = NOW() WHERE video_id = $2",
                is_online, video_id
            )

    async def count_videos(self) -> int:
        await self._ensure_connected()
        async with self.pool.acquire() as conn:
            return await conn.fetchval("SELECT COUNT(*) FROM videos")

    async def delete_video(self, video_id: str) -> bool:
        await self._ensure_connected()
        async with self.pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM videos WHERE video_id = $1", video_id
            )
            return result == "DELETE 1"

    async def get_stats(self) -> Dict:
        await self._ensure_connected()
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
        """Exportar todos os dados para backup."""
        await self._ensure_connected()
        async with self.pool.acquire() as conn:
            videos = await conn.fetch("SELECT * FROM videos ORDER BY created_at")
            configs = await conn.fetch("SELECT * FROM config")

            return {
                "version": "1.0",
                "exported_at": datetime.now().isoformat(),
                "videos": [dict(r) for r in videos],
                "config": [dict(r) for r in configs]
            }

    async def import_backup(self, backup_data: Dict) -> int:
        """Importar dados de um backup."""
        await self._ensure_connected()
        count = 0

        async with self.pool.acquire() as conn:
            for v in backup_data.get("videos", []):
                try:
                    await conn.execute("""
                        INSERT INTO videos (
                            video_id, title, file_id, telegram_message_id, telegram_channel_id,
                            telegram_link, player_url, file_size, duration, uploaded_by,
                            is_online, view_count, created_at
                        ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)
                        ON CONFLICT (video_id) DO UPDATE SET
                            title = EXCLUDED.title,
                            player_url = EXCLUDED.player_url,
                            telegram_link = EXCLUDED.telegram_link,
                            is_online = EXCLUDED.is_online,
                            view_count = EXCLUDED.view_count
                    """,
                    v["video_id"], v["title"], v["file_id"],
                    v.get("telegram_message_id"), v.get("telegram_channel_id"),
                    v.get("telegram_link"), v.get("player_url"),
                    v.get("file_size"), v.get("duration"), v.get("uploaded_by"),
                    v.get("is_online", True), v.get("view_count", 0),
                    v.get("created_at", datetime.now())
                    )
                    count += 1
                except Exception as e:
                    logger.error(f"Erro ao importar vídeo {v.get('video_id')}: {e}")

            for c in backup_data.get("config", []):
                try:
                    await conn.execute("""
                        INSERT INTO config (key, value, updated_at)
                        VALUES ($1, $2, $3)
                        ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
                    """, c["key"], c["value"], c.get("updated_at", datetime.now()))
                except Exception as e:
                    logger.error(f"Erro ao importar config {c.get('key')}: {e}")

        return count
