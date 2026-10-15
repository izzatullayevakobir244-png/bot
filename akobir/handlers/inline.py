from aiogram import Router, types
from aiogram.types import (
    InlineQueryResultCachedAudio,
    InlineQueryResultArticle,
    InputTextMessageContent,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from config import BOT_USERNAME
from database import get_cached_audio
from services.music_service import search_tracks

router = Router()

@router.inline_query()
async def inline_search_handler(inline_query: types.InlineQuery):
    query = inline_query.query.strip()
    if not query:
        # If query is empty, suggest default query
        query = "uzbek xit 2026"

    results = await search_tracks(query, limit=15)
    articles = []

    for item in results:
        vid_id = item["id"]
        title = item["title"]
        artist = item["artist"]
        duration = item.get("duration", 0)
        thumb = item.get("thumbnail")

        # Check if we have cached telegram file_id
        cached = await get_cached_audio(vid_id)
        if cached and cached.get("file_id"):
            articles.append(
                InlineQueryResultCachedAudio(
                    id=f"cached_{vid_id}",
                    audio_file_id=cached["file_id"],
                    caption=f"🎧 <b>{artist} — {title}</b>\n\n📥 <i>@{BOT_USERNAME} orqali yuklab olindi</i>",
                    parse_mode="HTML"
                )
            )
        else:
            # Article with direct link to bot /start <vid_id>
            bot_link = f"https://t.me/{BOT_USERNAME}?start={vid_id}"
            kb = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🎧 Yuklab olish / Tinglash", url=bot_link)
            ]])

            content_text = (
                f"🎧 <b>{artist} — {title}</b>\n"
                f"⏱ <b>Davomiyligi:</b> {item.get('duration_str', '00:00')}\n\n"
                f"📥 <i>@{BOT_USERNAME} orqali yuklab olish</i>"
            )

            articles.append(
                InlineQueryResultArticle(
                    id=vid_id,
                    title=f"{artist} - {title}",
                    description=f"⏱ {item.get('duration_str', '00:00')}",
                    thumbnail_url=thumb,
                    input_message_content=InputTextMessageContent(
                        message_text=content_text,
                        parse_mode="HTML"
                    ),
                    reply_markup=kb
                )
            )

    await inline_query.answer(
        results=articles,
        cache_time=60,
        is_personal=True
    )
