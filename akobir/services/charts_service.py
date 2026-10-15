from typing import List, Dict, Any
from services.music_service import search_tracks

CHART_CATEGORIES = {
    "uzbek": {
        "title": "🇺🇿 O'zbek xitlari",
        "query": "uzbek xit qoshiqlar 2025 2026 yangi"
    },
    "russian": {
        "title": "🇷🇺 Rus xitlari",
        "query": "russian hits 2025 2026 новинки чарт"
    },
    "global": {
        "title": "🌍 Jahon xitlari",
        "query": "billboard top global hits songs 2025 2026"
    },
    "fresh": {
        "title": "🆕 Yangi taronalar",
        "query": "yangi taronalar premiera 2025 2026"
    },
    "tiktok": {
        "title": "🔥 TikTok & Remix",
        "query": "tiktok mashup remix trend music 2025 2026"
    }
}

async def get_chart_tracks(category_key: str, limit: int = 10) -> List[Dict[str, Any]]:
    category = CHART_CATEGORIES.get(category_key)
    if not category:
        category = CHART_CATEGORIES["uzbek"]
    return await search_tracks(category["query"], limit=limit)
