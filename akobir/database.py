import aiosqlite
import datetime
import time
from typing import List, Dict, Optional, Any
from config import DB_PATH

# Fast in-memory caches for high-speed response
USER_LANG_CACHE: Dict[int, str] = {}
AUDIO_CACHE_MEMORY: Dict[str, Dict[str, Any]] = {}
CHANNELS_CACHE: Dict[str, Any] = {"time": 0.0, "data": []}

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                language TEXT DEFAULT 'uz',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS audio_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id TEXT UNIQUE,
                title TEXT,
                artist TEXT,
                duration INTEGER DEFAULT 0,
                file_id TEXT,
                thumbnail_url TEXT,
                file_size INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS favorites (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                video_id TEXT,
                title TEXT,
                artist TEXT,
                file_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, video_id)
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS mandatory_channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id TEXT UNIQUE,
                channel_title TEXT,
                channel_url TEXT
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS bot_stats (
                key TEXT PRIMARY KEY,
                value INTEGER DEFAULT 0
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS bot_settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)

        # Initialize stats if not present
        await db.execute("INSERT OR IGNORE INTO bot_stats (key, value) VALUES ('total_downloads', 0)")
        await db.execute("INSERT OR IGNORE INTO bot_stats (key, value) VALUES ('total_searches', 0)")
        await db.commit()

# --- Users operations ---
async def register_user(user_id: int, username: Optional[str], first_name: Optional[str]) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                await db.execute(
                    "UPDATE users SET username = ?, first_name = ?, last_active = CURRENT_TIMESTAMP WHERE user_id = ?",
                    (username, first_name, user_id)
                )
                await db.commit()
                return False
            else:
                await db.execute(
                    "INSERT INTO users (user_id, username, first_name, created_at, last_active) VALUES (?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
                    (user_id, username, first_name)
                )
                await db.commit()
                return True

async def get_user_language(user_id: int) -> str:
    if user_id in USER_LANG_CACHE:
        return USER_LANG_CACHE[user_id]
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT language FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            lang = row[0] if row and row[0] else "uz"
            USER_LANG_CACHE[user_id] = lang
            return lang

async def set_user_language(user_id: int, language: str):
    USER_LANG_CACHE[user_id] = language
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET language = ? WHERE user_id = ?", (language, user_id))
        await db.commit()

async def get_all_user_ids() -> List[int]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id FROM users") as cursor:
            rows = await cursor.fetchall()
            return [r[0] for r in rows]

async def get_users_count() -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0

# --- Audio Cache operations ---
async def get_cached_audio(video_id: str) -> Optional[Dict[str, Any]]:
    if video_id in AUDIO_CACHE_MEMORY:
        return AUDIO_CACHE_MEMORY[video_id]
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT video_id, title, artist, duration, file_id, thumbnail_url, file_size FROM audio_cache WHERE video_id = ?",
            (video_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                res = dict(row)
                AUDIO_CACHE_MEMORY[video_id] = res
                return res
            return None

async def save_audio_cache(video_id: str, title: str, artist: str, duration: int, file_id: str, thumbnail_url: str = "", file_size: int = 0):
    AUDIO_CACHE_MEMORY[video_id] = {
        "video_id": video_id,
        "title": title,
        "artist": artist,
        "duration": duration,
        "file_id": file_id,
        "thumbnail_url": thumbnail_url,
        "file_size": file_size
    }
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO audio_cache (video_id, title, artist, duration, file_id, thumbnail_url, file_size)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(video_id) DO UPDATE SET
                file_id = excluded.file_id,
                title = excluded.title,
                artist = excluded.artist,
                duration = excluded.duration,
                thumbnail_url = excluded.thumbnail_url,
                file_size = excluded.file_size
        """, (video_id, title, artist, duration, file_id, thumbnail_url, file_size))
        await db.commit()

# --- Favorites operations ---
async def add_favorite(user_id: int, video_id: str, title: str, artist: str, file_id: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            await db.execute("""
                INSERT INTO favorites (user_id, video_id, title, artist, file_id)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, video_id, title, artist, file_id))
            await db.commit()
            return True
        except aiosqlite.IntegrityError:
            return False

async def remove_favorite(user_id: int, video_id: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("DELETE FROM favorites WHERE user_id = ? AND video_id = ?", (user_id, video_id))
        await db.commit()
        return cursor.rowcount > 0

async def is_favorite(user_id: int, video_id: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id FROM favorites WHERE user_id = ? AND video_id = ?", (user_id, video_id)) as cursor:
            row = await cursor.fetchone()
            return bool(row)

async def get_user_favorites(user_id: int, limit: int = 20, offset: int = 0) -> List[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT video_id, title, artist, file_id FROM favorites WHERE user_id = ? ORDER BY id DESC LIMIT ? OFFSET ?",
            (user_id, limit, offset)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

async def count_user_favorites(user_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM favorites WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0

# --- Mandatory Channels operations ---
async def get_mandatory_channels() -> List[Dict[str, Any]]:
    now = time.time()
    if now - CHANNELS_CACHE["time"] < 60:
        return CHANNELS_CACHE["data"]
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT channel_id, channel_title, channel_url FROM mandatory_channels") as cursor:
            rows = await cursor.fetchall()
            data = [dict(r) for r in rows]
            CHANNELS_CACHE["time"] = now
            CHANNELS_CACHE["data"] = data
            return data

async def add_mandatory_channel(channel_id: str, title: str, url: str) -> bool:
    CHANNELS_CACHE["time"] = 0.0
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            await db.execute(
                "INSERT INTO mandatory_channels (channel_id, channel_title, channel_url) VALUES (?, ?, ?)",
                (channel_id, title, url)
            )
            await db.commit()
            return True
        except aiosqlite.IntegrityError:
            return False

async def remove_mandatory_channel(channel_id: str) -> bool:
    CHANNELS_CACHE["time"] = 0.0
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("DELETE FROM mandatory_channels WHERE channel_id = ?", (channel_id,))
        await db.commit()
        return cursor.rowcount > 0

# --- Statistics operations ---
async def increment_stat(key: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO bot_stats (key, value) VALUES (?, 1)
            ON CONFLICT(key) DO UPDATE SET value = value + 1
        """, (key,))
        await db.commit()

async def get_bot_stats() -> Dict[str, Any]:
    async with aiosqlite.connect(DB_PATH) as db:
        stats = {}
        async with db.execute("SELECT key, value FROM bot_stats") as cursor:
            rows = await cursor.fetchall()
            for k, v in rows:
                stats[k] = v
        async with db.execute("SELECT COUNT(*) FROM users") as cursor:
            row = await cursor.fetchone()
            stats["total_users"] = row[0] if row else 0
        async with db.execute("SELECT COUNT(*) FROM audio_cache") as cursor:
            row = await cursor.fetchone()
            stats["cached_songs"] = row[0] if row else 0
        return stats

# --- Bot Settings operations ---
async def get_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT value FROM bot_settings WHERE key = ?", (key,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else default

async def set_setting(key: str, value: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO bot_settings (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """, (key, value))
        await db.commit()
