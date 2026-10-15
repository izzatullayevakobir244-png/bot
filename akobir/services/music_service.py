import os
import re
import time
import json
import urllib.parse
import asyncio
import aiohttp
import uuid
from typing import List, Dict, Optional, Any
from pathlib import Path
import yt_dlp
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, TIT2, TPE1, TALB, APIC
import mutagen.id3

from config import FFMPEG_PATH, TEMP_DIR, BOT_NAME, BOT_USERNAME
from database import get_cached_audio, save_audio_cache, increment_stat

# High-speed search cache: query -> (timestamp, results)
SEARCH_QUERY_CACHE: Dict[str, tuple[float, List[Dict[str, Any]]]] = {}
CACHE_TTL = 3600  # 1 hour

def parse_duration_to_seconds(dur_str: str) -> int:
    try:
        parts = [int(p) for p in dur_str.split(":")]
        if len(parts) == 3:
            return parts[0] * 3600 + parts[1] * 60 + parts[2]
        elif len(parts) == 2:
            return parts[0] * 60 + parts[1]
        elif len(parts) == 1:
            return parts[0]
    except Exception:
        pass
    return 180

def clean_title(raw_title: str) -> tuple[str, str]:
    """
    Cleans raw title from YouTube and splits into (artist, title).
    For example: 'Xamdam Sobirov - Peshta (Official Video)' -> ('Xamdam Sobirov', 'Peshta')
    """
    cleaned = re.sub(r'\(.*?(official|video|klip|audio|lyric|remix|clip|music).*?\)', '', raw_title, flags=re.IGNORECASE)
    cleaned = re.sub(r'\[.*?(official|video|klip|audio|lyric|remix|clip|music).*?\]', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'(\bft\.?|\bfeat\.?).*?-', '-', cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.strip(" -_|#")

    if " - " in cleaned:
        parts = cleaned.split(" - ", 1)
        artist = parts[0].strip()
        title = parts[1].strip()
    elif " – " in cleaned:
        parts = cleaned.split(" – ", 1)
        artist = parts[0].strip()
        title = parts[1].strip()
    else:
        artist = BOT_NAME
        title = cleaned

    return artist, title

def format_duration(seconds: Optional[int]) -> str:
    if not seconds:
        return "00:00"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"

async def search_tracks_fast(query: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Ultra-fast direct asynchronous search querying YouTube results HTML.
    Parses ytInitialData directly in ~1.2s without heavy yt-dlp extractor overhead.
    """
    encoded = urllib.parse.quote_plus(query.strip())
    url = f"https://www.youtube.com/results?search_query={encoded}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9,uz;q=0.8"
    }

    results = []
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status == 200:
                    html = await resp.text()
                    match = re.search(r'var ytInitialData\s*=\s*({.+?});</script>', html)
                    if not match:
                        match = re.search(r'ytInitialData\s*=\s*({.+?});', html)

                    if match:
                        data = json.loads(match.group(1))
                        sections = data.get("contents", {}).get("twoColumnSearchResultsRenderer", {}).get("primaryContents", {}).get("sectionListRenderer", {}).get("contents", [])
                        for sec in sections:
                            items = sec.get("itemSectionRenderer", {}).get("contents", [])
                            for item in items:
                                v = item.get("videoRenderer")
                                if not v:
                                    continue
                                vid_id = v.get("videoId")
                                if not vid_id:
                                    continue

                                raw_title = "".join([r.get("text", "") for r in v.get("title", {}).get("runs", [])])
                                channel = "".join([r.get("text", "") for r in v.get("ownerText", {}).get("runs", [])])
                                dur_str = v.get("lengthText", {}).get("simpleText", "03:00")
                                dur_sec = parse_duration_to_seconds(dur_str)

                                c_artist, c_title = clean_title(raw_title)
                                if c_artist == BOT_NAME and channel:
                                    c_artist = channel

                                thumb = f"https://img.youtube.com/vi/{vid_id}/hqdefault.jpg"

                                results.append({
                                    "id": vid_id,
                                    "title": c_title,
                                    "artist": c_artist,
                                    "raw_title": raw_title,
                                    "duration": dur_sec,
                                    "duration_str": dur_str,
                                    "thumbnail": thumb,
                                    "url": f"https://www.youtube.com/watch?v={vid_id}"
                                })
                                if len(results) >= limit:
                                    break
                            if len(results) >= limit:
                                break
    except Exception as e:
        print(f"[Fast Search Error] {e}")

    return results

async def search_tracks_innertube(query: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Direct official YouTube InnerTube JSON API search.
    Response in ~0.8-1.2s without HTML scraping, never blocked by consent or cookies.
    """
    url = "https://www.youtube.com/youtubei/v1/search"
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept-Language": "uz-UZ,uz;q=0.9,ru;q=0.8,en;q=0.7"
    }
    payload = {
        "context": {
            "client": {
                "clientName": "WEB",
                "clientVersion": "2.20240301.00.00",
                "hl": "uz",
                "gl": "UZ"
            }
        },
        "query": query.strip()
    }

    results = []
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=4)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    sections = data.get("contents", {}).get("twoColumnSearchResultsRenderer", {}).get("primaryContents", {}).get("sectionListRenderer", {}).get("contents", [])
                    for sec in sections:
                        items = sec.get("itemSectionRenderer", {}).get("contents", [])
                        for item in items:
                            v = item.get("videoRenderer")
                            if not v:
                                continue
                            vid_id = v.get("videoId")
                            if not vid_id:
                                continue

                            raw_title = "".join([r.get("text", "") for r in v.get("title", {}).get("runs", [])])
                            channel = "".join([r.get("text", "") for r in v.get("ownerText", {}).get("runs", [])])
                            dur_str = v.get("lengthText", {}).get("simpleText", "03:00")
                            dur_sec = parse_duration_to_seconds(dur_str)

                            c_artist, c_title = clean_title(raw_title)
                            if c_artist == BOT_NAME and channel:
                                c_artist = channel

                            thumb = f"https://img.youtube.com/vi/{vid_id}/hqdefault.jpg"

                            results.append({
                                "id": vid_id,
                                "title": c_title,
                                "artist": c_artist,
                                "raw_title": raw_title,
                                "duration": dur_sec,
                                "duration_str": dur_str,
                                "thumbnail": thumb,
                                "url": f"https://www.youtube.com/watch?v={vid_id}"
                            })
                            if len(results) >= limit:
                                break
                        if len(results) >= limit:
                            break
    except Exception as e:
        print(f"[InnerTube Error] {e}")

    return results

async def search_tracks(query: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Searches tracks using memory cache -> InnerTube JSON API -> HTML parser -> yt-dlp fallback.
    """
    await increment_stat("total_searches")
    norm_query = query.strip().lower()
    now = time.time()

    # 1. In-memory cache hit (0.00004s)
    if norm_query in SEARCH_QUERY_CACHE:
        cached_time, cached_items = SEARCH_QUERY_CACHE[norm_query]
        if now - cached_time < CACHE_TTL:
            return cached_items[:limit]

    # 2. Ultra-fast direct InnerTube JSON API (~1.0s)
    innertube_results = await search_tracks_innertube(query, limit=limit)
    if innertube_results:
        SEARCH_QUERY_CACHE[norm_query] = (now, innertube_results)
        return innertube_results

    # 3. Fast HTML search fallback (~1.2s)
    fast_results = await search_tracks_fast(query, limit=limit)
    if fast_results:
        SEARCH_QUERY_CACHE[norm_query] = (now, fast_results)
        return fast_results


    # 3. Fallback to yt-dlp if direct search returned empty
    def _sync_search():
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'skip_download': True,
            'extract_flat': 'in_playlist',
            'default_search': f'ytsearch{limit}',
            'noplaylist': True,
            'socket_timeout': 10,
            'ffmpeg_location': FFMPEG_PATH,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                res = ydl.extract_info(f'ytsearch{limit}:{query}', download=False)
                if not res or 'entries' not in res:
                    return []
                results = []
                for entry in res['entries']:
                    if not entry:
                        continue
                    vid_id = entry.get('id')
                    raw_title = entry.get('title', 'Unknown')
                    duration = entry.get('duration') or 0
                    thumbnails = entry.get('thumbnails') or []
                    thumb_url = thumbnails[-1].get('url', '') if thumbnails else f"https://img.youtube.com/vi/{vid_id}/hqdefault.jpg"
                    artist, title = clean_title(raw_title)

                    results.append({
                        'id': vid_id,
                        'title': title,
                        'artist': artist,
                        'raw_title': raw_title,
                        'duration': duration,
                        'duration_str': format_duration(duration),
                        'thumbnail': thumb_url,
                        'url': f"https://www.youtube.com/watch?v={vid_id}"
                    })
                return results
            except Exception as e:
                print(f"[Search Fallback Error] {e}")
                return []

    fallback_results = await asyncio.to_thread(_sync_search)
    if fallback_results:
        SEARCH_QUERY_CACHE[norm_query] = (now, fallback_results)
    return fallback_results

from mutagen.mp4 import MP4, MP4Cover
import subprocess

async def download_track_mp3(video_id: str) -> Optional[Dict[str, Any]]:
    """
    Downloads track using high-speed audio-only stream (m4a/mp3).
    Bypasses heavy CPU re-encoding when native AAC audio is available.
    Tags with Mutagen (MP4 or MP3) and returns track info dict.
    Speed: ~2-4 seconds instead of 25-30 seconds!
    """
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    file_uid = uuid.uuid4().hex[:8]
    output_template = str(TEMP_DIR / f"{video_id}_{file_uid}.%(ext)s")
    final_audio_path = None

    def _sync_download():
        ydl_opts_primary = {
            'format': 'ba/b',
            'outtmpl': output_template,
            'socket_timeout': 10,
            'max_filesize': 50 * 1024 * 1024,
            'ffmpeg_location': FFMPEG_PATH,
            'quiet': True,
            'no_warnings': True,
            'noplaylist': True,
            'nopart': True,
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'web']
                }
            }
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts_primary) as ydl:
                info = ydl.extract_info(video_url, download=True)
                if not info:
                    raise Exception("Primary download returned no info")
                duration = info.get('duration') or 0
                if duration and duration > 1200:  # 20 minutes limit
                    return {'error': 'too_long', 'duration': duration}

                raw_title = info.get('title', 'Track')
                thumb_url = info.get('thumbnail', '')
                artist, title = clean_title(raw_title)
                return {
                    'title': title,
                    'artist': artist,
                    'duration': duration,
                    'thumbnail_url': thumb_url,
                    'video_id': video_id,
                    'raw_title': raw_title
                }
        except Exception as e:
            print(f"[Primary Android Download Failed] {e}, retrying with default client...")
            ydl_opts_fallback = {
                'format': 'ba/b',
                'outtmpl': output_template,
                'socket_timeout': 15,
                'max_filesize': 50 * 1024 * 1024,
                'ffmpeg_location': FFMPEG_PATH,
                'quiet': True,
                'no_warnings': True,
                'noplaylist': True,
                'nopart': True,
            }
            try:
                with yt_dlp.YoutubeDL(ydl_opts_fallback) as ydl_fb:
                    info = ydl_fb.extract_info(video_url, download=True)
                    if not info:
                        return None
                    duration = info.get('duration') or 0
                    if duration and duration > 1200:
                        return {'error': 'too_long', 'duration': duration}

                    raw_title = info.get('title', 'Track')
                    thumb_url = info.get('thumbnail', '')
                    artist, title = clean_title(raw_title)
                    return {
                        'title': title,
                        'artist': artist,
                        'duration': duration,
                        'thumbnail_url': thumb_url,
                        'video_id': video_id,
                        'raw_title': raw_title
                    }
            except Exception as fb_err:
                print(f"[Fallback Download Failed] {fb_err}")
                return None


    info = await asyncio.to_thread(_sync_download)
    if not info or info.get('error'):
        return info

    # Find the downloaded audio file
    downloaded_file = None
    for ext in ['.m4a', '.mp3', '.mp4', '.webm', '.opus', '.ogg', '.mkv']:
        p = TEMP_DIR / f"{video_id}_{file_uid}{ext}"
        if p.exists():
            downloaded_file = str(p)
            break

    if not downloaded_file:
        return None

    # Process into clean audio file (m4a or mp3)
    if downloaded_file.endswith(('.mp4', '.mkv')):
        m4a_out = str(TEMP_DIR / f"{video_id}_{file_uid}.m4a")
        def _extract_copy():
            cmd = [
                FFMPEG_PATH, '-y',
                '-i', downloaded_file,
                '-vn',
                '-c:a', 'copy',
                m4a_out
            ]
            res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return res.returncode == 0 and os.path.exists(m4a_out)

        success = await asyncio.to_thread(_extract_copy)
        if success:
            try:
                os.remove(downloaded_file)
            except Exception:
                pass
            final_audio_path = m4a_out
        else:
            mp3_out = str(TEMP_DIR / f"{video_id}_{file_uid}.mp3")
            def _quick_transcode():
                cmd = [
                    FFMPEG_PATH, '-y',
                    '-threads', '0',
                    '-i', downloaded_file,
                    '-vn',
                    '-c:a', 'libmp3lame',
                    '-q:a', '4',
                    mp3_out
                ]
                res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return res.returncode == 0 and os.path.exists(mp3_out)

            await asyncio.to_thread(_quick_transcode)
            try:
                os.remove(downloaded_file)
            except Exception:
                pass
            final_audio_path = mp3_out
    elif downloaded_file.endswith(('.webm', '.opus', '.ogg')):
        mp3_out = str(TEMP_DIR / f"{video_id}_{file_uid}.mp3")
        def _quick_transcode():
            cmd = [
                FFMPEG_PATH, '-y',
                '-threads', '0',
                '-i', downloaded_file,
                '-vn',
                '-c:a', 'libmp3lame',
                '-q:a', '4',
                mp3_out
            ]
            res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return res.returncode == 0 and os.path.exists(mp3_out)

        await asyncio.to_thread(_quick_transcode)
        try:
            os.remove(downloaded_file)
        except Exception:
            pass
        final_audio_path = mp3_out
    else:
        final_audio_path = downloaded_file


    # Download thumbnail cover data if available
    img_data = None
    if info.get('thumbnail_url'):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(info['thumbnail_url'], timeout=aiohttp.ClientTimeout(total=4)) as resp:
                    if resp.status == 200:
                        img_data = await resp.read()
        except Exception:
            pass

    # Tag audio file with Mutagen (MP4 or MP3)
    song_title = str(info.get('title') or info.get('raw_title') or "Musiqa")[:60]
    song_artist = str(info.get('artist') or (f"@{BOT_USERNAME}" if BOT_USERNAME else BOT_NAME))[:50]
    album_name = f"@{BOT_USERNAME}" if BOT_USERNAME else BOT_NAME

    try:
        if final_audio_path.endswith('.m4a'):
            mp4_audio = MP4(final_audio_path)
            mp4_audio['\xa9nam'] = [song_title]
            mp4_audio['\xa9ART'] = [song_artist]
            mp4_audio['\xa9alb'] = [album_name]
            if img_data:
                mp4_audio['covr'] = [MP4Cover(img_data, imageformat=MP4Cover.FORMAT_JPEG)]
            mp4_audio.save()
        elif final_audio_path.endswith('.mp3'):
            mp3_audio = MP3(final_audio_path, ID3=ID3)
            try:
                mp3_audio.add_tags()
            except mutagen.id3.error:
                pass
            mp3_audio.tags.add(TIT2(encoding=3, text=song_title))
            mp3_audio.tags.add(TPE1(encoding=3, text=song_artist))
            mp3_audio.tags.add(TALB(encoding=3, text=album_name))
            if img_data:
                mp3_audio.tags.add(APIC(
                    encoding=3,
                    mime='image/jpeg',
                    type=3,
                    desc='Cover',
                    data=img_data
                ))
            mp3_audio.save()
    except Exception as e:
        print(f"[Tagging Error] {e}")

    file_size = os.path.getsize(final_audio_path)
    info['file_path'] = final_audio_path
    info['file_size'] = file_size
    return info

