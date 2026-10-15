import re
import json
import logging
from typing import Dict, Any, Optional

import aiohttp
from config import GEMINI_API_KEY
from database import get_setting

logger = logging.getLogger("GeminiService")

# Vague / generic phrases that mean "I need music" without specifying any track
VAGUE_MUSIC_PATTERNS = [
    r'^(mana\s*)?shu\s*musiqa\s*(kerak|top|tashla|ber)?$',
    r'^menga\s*(bir\s*)?musiqa\s*kerak$',
    r'^manga\s*(bir\s*)?musiqa\s*kerak$',
    r'^(mana\s*)?shu\s*qo[\'’`]?shiq\s*(kerak|top|tashla|ber)?$',
    r'^(mana\s*)?shu\s*ashula\s*(kerak|top|tashla|ber)?$',
    r'^(mana\s*)?shu\s*tarona\s*(kerak|top|tashla|ber)?$',
    r'^musiqa\s*(kerak|top|tashla|ber|izlayapman)$',
    r'^qo[\'’`]?shiq\s*(kerak|top|tashla|ber|izlayapman)$',
    r'^ashula\s*(kerak|top|tashla|ber)$',
    r'^bitta\s*(yaxshi\s*)?(musiqa|qo[\'’`]?shiq|ashula)\s*(kerak|tashla|ber)?$',
    r'^topib\s*ber(chi)?$',
    r'^musiqani\s*top(ib\s*ber)?$',
    r'^musiqa\s*qidirish$',
    r'^track\s*kerak$',
    r'^manga\s*musiqa\s*kerak$',
    r'^menga\s*musiqa\s*kerak$',
    r'^manashu\s*musiqa\s*kerak$',
    r'^shu\s*musiqa\s*kerak$',
    r'^эту\s*музыку\s*(скинь|найди|хочу)?$',
    r'^мне\s*нужна\s*(эта\s*)?музыка$',
    r'^мне\s*нужна\s*(эта\s*)?песня$',
    r'^найди\s*(мне\s*)?песню$',
    r'^скинь\s*(мне\s*)?музыку$',
    r'^хочу\s*музыку$',
    r'^i\s*need\s*(this\s*)?music$',
    r'^find\s*(this\s*)?song$',
]

# Conversational stop-phrases to strip in rule-based cleaning
STOP_PHRASES = [
    r'\bmanashu\s+musiqa\s+kerak\b',
    r'\bshu\s+musiqa\s+kerak\b',
    r'\bmenga\b',
    r'\bmanga\b',
    r'\bbizga\b',
    r'\biltimos\b',
    r'\btopib\s+bering\b',
    r'\btopib\s+bersang\b',
    r'\btopib\s+berchi\b',
    r'\btopib\s+ber\b',
    r'\btopvor\b',
    r'\bizlab\s+ber\b',
    r'\bmusiqasi\s+kerak\b',
    r'\bmusiqasi\b',
    r'\bqo[\'’`]?shig[\'’`]?i\s+kerak\b',
    r'\bqo[\'’`]?shig[\'’`]?i\b',
    r'\btaronasi\s+kerak\b',
    r'\btaronasi\b',
    r'\bashulasi\s+kerak\b',
    r'\bashulasi\b',
    r'\btreki\s+kerak\b',
    r'\btreki\b',
    r'\bdegan\s+musiqa\b',
    r'\bdegan\s+qo[\'’`]?shiq\b',
    r'\bdegan\s+ashula\b',
    r'\bdegan\b',
    r'\bnomli\b',
    r'\bkerak\b',
    r'\byangi\s+xit\b',
    r'\byangi\s+chiqqan\b',
    r'\bmana\s+shu\b',
    r'\bmanashu\b',
    r'\bshu\b',
    r'\bмне\s+нужна\b',
    r'\bмне\s+нужен\b',
    r'\bнайди\s+мне\b',
    r'\bнайди\s+песню\b',
    r'\bнайди\s+трек\b',
    r'\bскинь\s+песню\b',
    r'\bскинь\s+музыку\b',
    r'\bпожалуйста\b',
]

def is_vague_request(text: str) -> bool:
    """Returns True if the text is a vague statement like 'manashu musiqa kerak' with no track details."""
    clean = text.strip().lower()
    for pattern in VAGUE_MUSIC_PATTERNS:
        if re.search(pattern, clean):
            return True
    return False

def clean_conversational_text(text: str) -> str:
    """Strips conversational clutter (e.g. 'menga Xamdam Sobirovning holimga qara qo'shig'i kerak' -> 'Xamdam Sobirov holimga qara')."""
    cleaned = text.strip()
    for pattern in STOP_PHRASES:
        cleaned = re.sub(pattern, ' ', cleaned, flags=re.IGNORECASE)
    # Remove redundant punctuation & whitespace
    cleaned = re.sub(r'[«»""\'\(\)\[\]\?\!\.,]', ' ', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned

async def get_active_gemini_key() -> str:
    """Returns the Gemini API key from environment or database."""
    if GEMINI_API_KEY:
        return GEMINI_API_KEY
    db_key = await get_setting("gemini_api_key")
    return db_key or ""

async def analyze_music_request(user_text: str, reply_text: Optional[str] = None) -> Dict[str, Any]:
    """
    Intelligently analyzes user query using Gemini AI (with bulletproof regex fallback).
    Handles:
    - Vague requests ("manashu musiqa kerak" -> asks for details)
    - Natural language queries ("menga falonchining falon qoshigi kerak" -> extracts artist & title)
    - Lyrics / descriptions ("yuragim sezar sen kelmaysan..." -> identifies exact song)
    - Greetings / music questions -> chat response
    """
    raw_query = user_text.strip()
    norm_query = raw_query.lower()

    # 1. Quick check for vague request without any detail
    if is_vague_request(norm_query):
        return {
            "action": "need_info",
            "message": (
                "🎧 <b>Qaysi musiqa kerak?</b>\n\n"
                "Iltimos, quyidagilardan birini yuboring:\n"
                "• Qo'shiq nomi yoki ijrochisi (masalan: <code>Xamdam Sobirov - Peshta</code>)\n"
                "• Qo'shiq so'zlaridan bir qator (matn bo'yicha qidirish)\n"
                "• Ovozli xabar (voice)\n"
                "• Yoki videoni botga yuboring — musiqasini ajratib beraman! ⚡️"
            )
        }

    # 2. Check if query is already clean and short (e.g. "Peshta", "Xamdam Sobirov", "Lady Gaga Bad Romance")
    # If no conversational words exist, bypass AI to save time and return immediate search
    cleaned_rule = clean_conversational_text(raw_query)
    has_conversational_words = any(re.search(p, raw_query, re.IGNORECASE) for p in STOP_PHRASES)
    is_lyrics_likely = len(raw_query.split()) >= 5 or any(w in norm_query for w in ["so'zlari", "sozlari", "matni", "слова", "lyrics", "aytiladi"])

    api_key = await get_active_gemini_key()

    # If Gemini is available and the query is complex, conversational, or has lyrics:
    if api_key and (has_conversational_words or is_lyrics_likely or len(raw_query) > 30):
        try:
            ai_result = await _call_gemini_api(api_key, raw_query, reply_text)
            if ai_result:
                return ai_result
        except Exception as e:
            logger.warning(f"Gemini API error, falling back to rule-based: {e}")

    # 3. Rule-based fallback
    if cleaned_rule and len(cleaned_rule) >= 2:
        return {
            "action": "search",
            "clean_query": cleaned_rule,
            "raw_query": raw_query,
            "artist": "",
            "title": cleaned_rule
        }

    # If stripped query ended up empty
    return {
        "action": "need_info",
        "message": (
            "🔍 <b>Iltimos, aniqroq qo'shiq nomi yoki ijrochisini yozing</b>\n"
            "Masalan: <code>Jaloliddin Ahmadaliyev</code> yoki <code>Xamdam Sobirov</code>"
        )
    }

async def _call_gemini_api(api_key: str, text: str, reply_text: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Calls Gemini REST API directly for maximum speed (< 600ms) and reliability."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"

    prompt = f"""
Sen Telegram musiqa boti uchun aqlli musiqa yordamchisisan.
Foydalanuvchi xabarlarini tahlil qilasan (o'zbekcha, ruscha, inglizcha).

Foydalanuvchi xabari: "{text}"
{f'Javob berilgan xabar: "{reply_text}"' if reply_text else ''}

Qoidalarga asosan faqat toza JSON formatida javob qaytar:
1. Agar foydalanuvchi qo'shiq qidirayotgan bo'lsa (tabiiy tilda, qo'shiq so'zlari yoki tavsif orqali):
   - Agar qo'shiq so'zlari yoki tavsif bo'lsa, haqiqiy ijrochi va qo'shiq nomini aniqla!
   - JSON:
     {{
       "action": "search",
       "clean_query": "Ijrochi - Qo'shiq nomi",
       "artist": "Ijrochi",
       "title": "Qo'shiq nomi",
       "explanation": "Qisqa tushuntirish (agar so'zlardan aniqlangan bo'lsa)"
     }}

2. Agar foydalanuvchi qaysi qo'shiq ekanligini aytmasdan shunchaki "manashu musiqa kerak", "bitta musiqa ber", "topib ber", "musiqa kerak" degan bo'lsa:
   - JSON:
     {{
       "action": "need_info",
       "message": "Qaysi qo'shiq kerak? Qo'shiq nomi, ijrochini yozing yoki so'zlaridan yuboring (yoki ovozli xabar jo'nating)!"
     }}

3. Agar foydalanuvchi salomlashsa yoki umumiy suhbatlashsa:
   - JSON:
     {{
       "action": "chat",
       "message": "Do'stona qisqa javob va musiqa topib bera olishing haqida eslatma"
     }}

Faqat JSON formatda javob ber, hech qanday qo'shimcha belgisiz (markdown codeblocksiz).
"""

    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 300
        }
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=4)) as resp:
            if resp.status != 200:
                # If gemini-2.0-flash is unavailable, try gemini-1.5-flash
                alt_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
                async with session.post(alt_url, json=payload, timeout=aiohttp.ClientTimeout(total=4)) as resp2:
                    if resp2.status != 200:
                        return None
                    data = await resp2.json()
            else:
                data = await resp.json()

            candidates = data.get("candidates", [])
            if not candidates:
                return None

            content_parts = candidates[0].get("content", {}).get("parts", [])
            if not content_parts:
                return None

            raw_text = content_parts[0].get("text", "").strip()
            # Clean markdown codeblocks if any
            clean_json = re.sub(r'^```(json)?\s*', '', raw_text, flags=re.IGNORECASE)
            clean_json = re.sub(r'\s*```$', '', clean_json).strip()

            parsed = json.loads(clean_json)
            return parsed
