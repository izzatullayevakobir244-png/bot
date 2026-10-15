import aiohttp
import urllib.parse
from typing import Optional, Dict

async def get_lyrics(title: str, artist: str = "") -> Optional[Dict[str, str]]:
    """
    Fetches lyrics using LRCLIB API.
    Returns dict with { 'title': ..., 'artist': ..., 'lyrics': ... } or None.
    """
    query = f"{artist} {title}".strip()
    url = f"https://lrclib.net/api/search?q={urllib.parse.quote(query)}"

    headers = {
        "User-Agent": "MyMusicBot/1.0 (https://t.me/MyMusic_bot)"
    }

    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=6)) as response:
                if response.status == 200:
                    data = await response.json()
                    if data and isinstance(data, list) and len(data) > 0:
                        first = data[0]
                        lyrics = first.get("plainLyrics")
                        if not lyrics and first.get("syncedLyrics"):
                            # clean timestamps from synced lyrics
                            import re
                            lyrics = re.sub(r'\[\d+:\d+\.\d+\]', '', first.get("syncedLyrics")).strip()

                        if lyrics:
                            return {
                                "title": first.get("trackName", title),
                                "artist": first.get("artistName", artist),
                                "lyrics": lyrics
                            }
    except Exception as e:
        print(f"[Lyrics Error] {e}")

    return None
