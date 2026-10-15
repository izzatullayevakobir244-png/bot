import os
import re
import uuid
import asyncio
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any

import yt_dlp
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, TIT2, TPE1, TALB, COMM
import mutagen.id3

from config import FFMPEG_PATH, TEMP_DIR, BOT_NAME, BOT_USERNAME, BASE_DIR

MEDIA_URL_REGEX = re.compile(
    r'(https?://(?:www\.)?(?:instagram\.com|instagr\.am|tiktok\.com|vt\.tiktok\.com|youtube\.com/shorts|youtu\.be|facebook\.com|fb\.watch|pin\.it|pinterest\.com)/[^\s]+)',
    re.IGNORECASE
)

def is_media_url(text: str) -> bool:
    """Checks whether the text contains a supported media URL (Instagram, TikTok, YouTube Shorts, etc.)."""
    return bool(MEDIA_URL_REGEX.search(text.strip()))

def extract_media_url(text: str) -> Optional[str]:
    """Extracts the first media URL from text."""
    match = MEDIA_URL_REGEX.search(text.strip())
    if match:
        return match.group(1)
    return None

def format_duration(seconds: Optional[int]) -> str:
    if not seconds:
        return "00:00"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"

async def extract_audio_from_video(
    video_path: str,
    title: str = "Video Musiqasi",
    artist: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Extracts high-quality MP3 audio from a video file using FFmpeg,
    and tags it with ID3 metadata.
    """
    if not os.path.exists(video_path):
        return None

    if not artist:
        artist = f"@{BOT_USERNAME}" if BOT_USERNAME else BOT_NAME

    uid = uuid.uuid4().hex[:8]
    mp3_path = str(TEMP_DIR / f"extracted_{uid}.mp3")

    cmd = [
        FFMPEG_PATH,
        "-y",
        "-threads", "0",
        "-i", video_path,
        "-vn",
        "-acodec", "libmp3lame",
        "-b:a", "192k",
        "-ar", "44100",
        mp3_path
    ]

    def _run_ffmpeg():
        res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return res.returncode == 0

    success = await asyncio.to_thread(_run_ffmpeg)
    if not success or not os.path.exists(mp3_path):
        return None

    # Calculate duration and tag MP3
    duration = 0
    file_size = os.path.getsize(mp3_path)
    try:
        audio = MP3(mp3_path, ID3=ID3)
        duration = int(audio.info.length)
        try:
            audio.add_tags()
        except mutagen.id3.error:
            pass

        clean_title = (title[:60] if title else "Video Musiqasi").strip()
        audio.tags.add(TIT2(encoding=3, text=clean_title))
        audio.tags.add(TPE1(encoding=3, text=artist[:50]))
        audio.tags.add(TALB(encoding=3, text=f"@{BOT_USERNAME}"))
        audio.tags.add(COMM(encoding=3, lang="eng", desc="Bot", text=f"Downloaded via @{BOT_USERNAME}"))
        audio.save()
    except Exception as e:
        print(f"[Tagging extracted audio error] {e}")

    return {
        "file_path": mp3_path,
        "title": clean_title,
        "artist": artist,
        "duration": duration,
        "duration_str": format_duration(duration),
        "file_size": file_size
    }

async def download_media_from_url(url: str) -> Optional[Dict[str, Any]]:
    """
    Downloads media (video) from Instagram, TikTok, YouTube Shorts, etc. using yt-dlp.
    Supports cookies.txt if present in project root.
    Returns info dict with 'video_path', 'caption', 'title', 'duration', etc.
    """
    uid = uuid.uuid4().hex[:8]
    output_template = str(TEMP_DIR / f"media_{uid}.%(ext)s")

    cookies_file = BASE_DIR / "cookies.txt"

    def _sync_download():
        ydl_opts = {
            'outtmpl': output_template,
            'format': 'best[ext=mp4]/best',
            'socket_timeout': 15,
            'ffmpeg_location': FFMPEG_PATH,
            'quiet': True,
            'no_warnings': True,
            'noplaylist': True,
            'nopart': True,
            'max_filesize': 50 * 1024 * 1024,  # Telegram bot limit 50MB
        }
        if cookies_file.exists():
            ydl_opts['cookiefile'] = str(cookies_file)

        # For Instagram / YouTube / TikTok args
        ydl_opts['extractor_args'] = {
            'youtube': {'player_client': ['android', 'web']}
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(url, download=True)
                if not info:
                    return None

                filename = ydl.prepare_filename(info)
                # Some postprocessors might change ext to mp4
                if not os.path.exists(filename):
                    base = os.path.splitext(filename)[0]
                    for ext in [".mp4", ".mkv", ".webm"]:
                        if os.path.exists(base + ext):
                            filename = base + ext
                            break

                if not os.path.exists(filename):
                    return None

                caption = info.get("description") or info.get("title") or ""
                # Strip excessive hashtags / URLs for cleaner caption
                title = info.get("title") or "Video"
                author = info.get("uploader") or info.get("channel") or ""
                duration = info.get("duration") or 0

                return {
                    "video_path": filename,
                    "caption": caption.strip(),
                    "title": title.strip(),
                    "author": author.strip(),
                    "duration": int(duration),
                    "file_size": os.path.getsize(filename)
                }
            except Exception as e:
                print(f"[Media Download Error] {e}")
                return None

    return await asyncio.to_thread(_sync_download)
