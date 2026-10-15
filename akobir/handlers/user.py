import os
import uuid
from typing import Dict, Any, List
from aiogram import Router, F, types
from aiogram.filters import CommandStart, Command
from aiogram.types import FSInputFile, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from config import BOT_NAME, BOT_USERNAME
from database import (
    register_user, get_user_language, set_user_language,
    get_cached_audio, save_audio_cache,
    add_favorite, remove_favorite, is_favorite,
    increment_stat
)
from services.music_service import search_tracks, download_track_mp3, format_duration
from services.gemini_service import analyze_music_request
from services.lyrics_service import get_lyrics
from services.media_service import (
    is_media_url,
    extract_media_url,
    download_media_from_url,
    extract_audio_from_video
)
from keyboards.reply import get_main_keyboard
from keyboards.inline import (
    get_search_results_keyboard,
    get_track_actions_keyboard,
    get_settings_keyboard
)

router = Router()

# In-memory session cache for pagination
SEARCH_CACHE: Dict[str, List[Dict[str, Any]]] = {}

@router.message(CommandStart())
async def cmd_start(message: types.Message):
    user = message.from_user
    await register_user(user.id, user.username, user.first_name)
    lang = await get_user_language(user.id)

    # Check for deep-linking (e.g., /start <video_id>)
    args = message.text.split(maxsplit=1)
    if len(args) > 1:
        param = args[1].strip()
        if len(param) >= 8:
            await handle_download(message, param, user.id, lang)
            return

    welcome_text = (
        f"👋 <b>Assalomu alaykum, {user.first_name}!</b>\n\n"
        f"🎧 <b>{BOT_NAME}</b> ga xush kelibsiz!\n\n"
        "Men orqali istalgan taronani yuqori sifatda (192 kbps) topishingiz va yuklab olishingiz mumkin.\n\n"
        "📌 <b>Imkoniyatlar:</b>\n"
        "• Qo'shiq nomi yoki ijrochisini yozib yuboring\n"
        "• Ovozli xabar (voice) yoki audio yuborib qidiring\n"
        "• 📥 Instagram / TikTok havolasini yuboring (video + MP3 musiqa)\n"
        "• 🎬 Har qanday videoni yuboring — musiqasi va matnini ajratib beraman\n"
        "• 🔝 Top va yangi xit taronalarni tinglang\n"
        f"• Har qanday guruh yoki chatda <code>@{BOT_USERNAME} qo'shiq</code> deb qidiring\n\n"
        "🔍 <i>Qidirish uchun shunchaki qo'shiq nomi yoki havola yuboring:</i>"
    )

    if lang == "ru":
        welcome_text = (
            f"👋 <b>Привет, {user.first_name}!</b>\n\n"
            f"🎧 Добро пожаловать в <b>{BOT_NAME}</b>!\n\n"
            "Здесь вы можете искать и скачивать любую музыку в высоком качестве (192 kbps).\n\n"
            "📌 <b>Возможности:</b>\n"
            "• Отправьте название песни или имя исполнителя\n"
            "• Отправьте голосовое сообщение для поиска\n"
            "• 📥 Отправьте ссылку Instagram / TikTok (видео + MP3 музыка)\n"
            "• 🎬 Отправьте любое видео — бот извлечет музыку и текст\n"
            "• Слушайте топ треки и новинки\n"
            f"• Инлайн поиск: <code>@{BOT_USERNAME} название</code> в любом чате\n\n"
            "🔍 <i>Для поиска просто напишите название песни или отправьте ссылку:</i>"
        )
    elif lang == "en":
        welcome_text = (
            f"👋 <b>Welcome, {user.first_name}!</b>\n\n"
            f"🎧 Welcome to <b>{BOT_NAME}</b>!\n\n"
            "Find and download your favorite songs in high quality (192 kbps).\n\n"
            "📌 <b>Features:</b>\n"
            "• Send song title or artist name\n"
            "• Send voice message to search\n"
            "• 📥 Send Instagram / TikTok link (video + MP3 music)\n"
            "• 🎬 Send any video — extract audio and caption\n"
            "• Browse top trending music\n"
            f"• Inline search: <code>@{BOT_USERNAME} query</code>\n\n"
            "🔍 <i>Type song name or send link to start searching:</i>"
        )

    await message.answer(welcome_text, reply_markup=get_main_keyboard(user.id, lang), parse_mode="HTML")

@router.message(F.text == "🔍 Musiqa qidirish")
@router.message(F.text == "🔍 Поиск музыки")
@router.message(F.text == "🔍 Search Music")
async def btn_search(message: types.Message):
    lang = await get_user_language(message.from_user.id)
    text = "🔍 <b>Iltimos, qo'shiq nomi yoki ijrochini yozib yuboring:</b>"
    if lang == "ru":
        text = "🔍 <b>Введите название песни или исполнителя:</b>"
    elif lang == "en":
        text = "🔍 <b>Please send song title or artist name:</b>"
    await message.answer(text, parse_mode="HTML")

@router.message(F.text == "ℹ️ Bot haqida")
@router.message(F.text == "ℹ️ О боте")
@router.message(F.text == "ℹ️ About Bot")
async def btn_about(message: types.Message):
    lang = await get_user_language(message.from_user.id)
    text = (
        f"🎧 <b>{BOT_NAME}</b> — eng tezkor va qulay musiqa Telegram boti!\n\n"
        "⚡️ <b>Tezlik:</b> Kesh tizimi orqali soniyalarda yuklab beradi\n"
        "🎶 <b>Sifat:</b> 192 kbps yuqori sifatli MP3 va albom muqovasi\n"
        "🎤 <b>Ovozli qidiruv:</b> Ovozli xabar orqali qo'shiqni topish\n"
        "📜 <b>Matn:</b> Qo'shiq so'zlarini (lyrics) ko'rish imkoniyati\n\n"
        f"Do'stlaringizga ulashing: @{BOT_USERNAME}"
    )
    if lang == "ru":
        text = (
            f"🎧 <b>{BOT_NAME}</b> — быстрый и удобный музыкальный бот!\n\n"
            "⚡️ <b>Скорость:</b> Мгновенная отправка треков через кэш\n"
            "🎶 <b>Качество:</b> Высокое качество MP3 с обложками\n"
            "🎤 <b>Голосовой поиск:</b> Распознавание голосовых сообщений\n"
            "📜 <b>Тексты песен:</b> Поиск слов к песням\n\n"
            f"Поделиться с друзьями: @{BOT_USERNAME}"
        )
    elif lang == "en":
        text = (
            f"🎧 <b>{BOT_NAME}</b> — fast and modern music downloader bot!\n\n"
            "⚡️ <b>Speed:</b> Instant delivery via smart caching\n"
            "🎶 <b>Quality:</b> High quality MP3 with album artwork\n"
            "🎤 <b>Voice search:</b> Search via voice notes\n"
            "📜 <b>Lyrics:</b> View lyrics for tracks\n\n"
            f"Share with friends: @{BOT_USERNAME}"
        )
    await message.answer(text, parse_mode="HTML")

@router.message(F.text == "⚙️ Sozlamalar")
@router.message(F.text == "⚙️ Настройки")
@router.message(F.text == "⚙️ Settings")
async def btn_settings(message: types.Message):
    lang = await get_user_language(message.from_user.id)
    text = "⚙️ <b>Tilni tanlang / Выберите язык / Select language:</b>"
    await message.answer(text, reply_markup=get_settings_keyboard(lang), parse_mode="HTML")

@router.callback_query(F.data.startswith("setlang:"))
async def cb_setlang(callback: CallbackQuery):
    new_lang = callback.data.split(":")[1]
    await set_user_language(callback.from_user.id, new_lang)
    success_text = "✅ Til muvaffaqiyatli o'zgartirildi!"
    if new_lang == "ru":
        success_text = "✅ Язык успешно изменен!"
    elif new_lang == "en":
        success_text = "✅ Language changed successfully!"
    await callback.answer(success_text)
    await callback.message.edit_reply_markup(reply_markup=get_settings_keyboard(new_lang))
    await callback.message.answer(
        success_text,
        reply_markup=get_main_keyboard(callback.from_user.id, new_lang)
    )

# --- Music Search Handler ---
@router.message(F.text)
async def handle_search_query(message: types.Message):
    query = message.text.strip()
    user_id = message.from_user.id
    lang = await get_user_language(user_id)

    if query.startswith("/"):
        return

    if query in ["❌ Bekor qilish", "❌ Отмена", "❌ Cancel"]:
        await message.answer("🏠 Asosiy menyu", reply_markup=get_main_keyboard(user_id, lang))
        return

    # Check if this message is replying to a media (e.g. video/voice/audio)
    if message.reply_to_message:
        rep = message.reply_to_message
        if rep.video:
            status_msg = await message.answer(
                "⚡️ <b>Ushbu videodan musiqa ajratib olinmoqda...</b>" if lang == "uz" else
                ("⚡️ <b>Извлечение аудио из этого видео...</b>" if lang == "ru" else "⚡️ <b>Extracting audio from this video...</b>"),
                parse_mode="HTML"
            )
            bot = message.bot
            temp_vid = str(TEMP_DIR / f"rep_{uuid.uuid4().hex[:8]}.mp4")
            try:
                f_info = await bot.get_file(rep.video.file_id)
                await bot.download_file(f_info.file_path, temp_vid)
                song_t = rep.caption[:50].strip() if rep.caption else "Video Musiqasi"
                audio_res = await extract_audio_from_video(
                    temp_vid,
                    title=song_t,
                    artist=f"@{BOT_USERNAME}" if BOT_USERNAME else BOT_NAME
                )
                if audio_res and os.path.exists(audio_res["file_path"]):
                    song_uid = f"rep_{uuid.uuid4().hex[:8]}"
                    file_size_mb = round(audio_res["file_size"] / (1024 * 1024), 1)
                    caption = (
                        f"🎧 <b>{audio_res['artist']} — {audio_res['title']}</b>\n\n"
                        f"⏱ <b>Davomiyligi:</b> {audio_res['duration_str']}\n"
                        f"💾 <b>Hajmi:</b> {file_size_mb} MB\n\n"
                        f"🤖 <b>@{BOT_USERNAME}</b> — <i>Eng sara taronalar!</i>"
                    )
                    kb = get_track_actions_keyboard(song_uid, is_saved=False, lang=lang)
                    sent_a = await message.answer_audio(
                        audio=FSInputFile(audio_res["file_path"]),
                        title=audio_res["title"],
                        performer=audio_res["artist"],
                        duration=audio_res["duration"],
                        caption=caption,
                        reply_markup=kb,
                        parse_mode="HTML"
                    )
                    await save_audio_cache(
                        video_id=song_uid,
                        title=audio_res["title"],
                        artist=audio_res["artist"],
                        duration=audio_res["duration"],
                        file_id=sent_a.audio.file_id,
                        thumbnail_url="",
                        file_size=audio_res["file_size"]
                    )
                    try:
                        await status_msg.delete()
                    except Exception:
                        pass
                    return
            except Exception as e:
                print(f"[Reply Video Error] {e}")
                await status_msg.edit_text("❌ Videodan audio ajratishda xatolik yuz berdi.")
                return
            finally:
                if os.path.exists(temp_vid):
                    try:
                        os.remove(temp_vid)
                    except Exception:
                        pass

    # Check if input is a media URL (Instagram, TikTok, YouTube Shorts, etc.)
    if is_media_url(query):
        await handle_media_download(message, query, user_id, lang)
        return

    # Analyze query using Gemini AI + smart conversational rules
    rep_text = message.reply_to_message.text if message.reply_to_message else None
    analysis = await analyze_music_request(query, reply_text=rep_text)

    action = analysis.get("action", "search")
    if action == "need_info":
        await message.answer(analysis.get("message", "Qaysi musiqa kerak? Qo'shiq nomini yozing!"), parse_mode="HTML")
        return

    if action == "chat":
        await message.answer(analysis.get("message", "Assalomu alaykum!"), parse_mode="HTML")
        return

    target_query = analysis.get("clean_query") or query
    explanation = analysis.get("explanation")

    search_status_text = (
        f"💡 <i>{explanation}</i>\n🔎 <b>Qidirilmoqda...</b>" if explanation else
        ("🔎 <b>Qidirilmoqda...</b>" if lang == "uz" else ("🔎 <b>Поиск...</b>" if lang == "ru" else "🔎 <b>Searching...</b>"))
    )

    searching_msg = await message.answer(search_status_text, parse_mode="HTML")

    results = await search_tracks(target_query, limit=10)
    # If no results and title was separated, try searching title alone
    if not results and analysis.get("title") and analysis.get("title") != target_query:
        results = await search_tracks(analysis["title"], limit=10)

    if not results:
        not_found = (
            f"😔 <b>«{target_query}» bo'yicha hech qanday qo'shiq topilmadi.</b>\nBoshqa nom yoki ijrochi bilan qidirib ko'ring."
            if lang == "uz" else
            (f"😔 <b>По запросу «{target_query}» ничего не найдено.</b>\nПопробуйте другой запрос." if lang == "ru" else f"😔 <b>No tracks found for «{target_query}».</b>\nTry another query.")
        )
        await searching_msg.edit_text(not_found, parse_mode="HTML")
        return

    # Cache results for pagination (5 per page)
    session_id = uuid.uuid4().hex[:10]
    SEARCH_CACHE[session_id] = results

    await send_search_page(searching_msg, session_id, page=0, lang=lang, is_edit=True)


EMOJI_NUMS = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]

async def send_search_page(message: types.Message, session_id: str, page: int, lang: str = "uz", is_edit: bool = False):
    results = SEARCH_CACHE.get(session_id, [])
    if not results:
        return

    page_size = 5
    total_pages = (len(results) + page_size - 1) // page_size
    start_idx = page * page_size
    page_items = results[start_idx:start_idx + page_size]

    text_lines = [
        "🔎 <b>Qidiruv natijalari:</b>\n" if lang == "uz" else
        ("🔎 <b>Результаты поиска:</b>\n" if lang == "ru" else "🔎 <b>Search results:</b>\n")
    ]

    for i, item in enumerate(page_items, start=1):
        num_emoji = EMOJI_NUMS[i - 1] if i <= len(EMOJI_NUMS) else f"{i}."
        text_lines.append(f"{num_emoji} <b>{item['artist']}</b> — {item['title']} <code>[{item['duration_str']}]</code>")

    text_lines.append(
        "\n📥 <i>Yuklab olish uchun pastdagi raqamni tanlang:</i>" if lang == "uz" else
        ("\n📥 <i>Нажмите на номер ниже для скачивания:</i>" if lang == "ru" else "\n📥 <i>Tap the number below to download:</i>")
    )

    full_text = "\n".join(text_lines)
    kb = get_search_results_keyboard(page_items, page, total_pages, session_id)

    if is_edit:
        await message.edit_text(full_text, reply_markup=kb, parse_mode="HTML")
    else:
        await message.answer(full_text, reply_markup=kb, parse_mode="HTML")

@router.callback_query(F.data.startswith("page:"))
async def cb_pagination(callback: CallbackQuery):
    parts = callback.data.split(":")
    session_id = parts[1]
    page = int(parts[2])
    lang = await get_user_language(callback.from_user.id)
    await send_search_page(callback.message, session_id, page, lang=lang, is_edit=True)
    await callback.answer()

@router.callback_query(F.data == "close_search")
async def cb_close_search(callback: CallbackQuery):
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.answer()

@router.callback_query(F.data == "noop")
async def cb_noop(callback: CallbackQuery):
    await callback.answer()

# --- Download & Audio Dispatch Handler ---
@router.callback_query(F.data.startswith("dl:"))
async def cb_download(callback: CallbackQuery):
    video_id = callback.data.split(":")[1]
    user_id = callback.from_user.id
    lang = await get_user_language(user_id)
    await callback.answer(
        "⏳ Yuklab olinmoqda..." if lang == "uz" else ("⏳ Скачивание..." if lang == "ru" else "⏳ Downloading...")
    )
    await handle_download(callback.message, video_id, user_id, lang)

async def handle_download(context_msg: types.Message, video_id: str, user_id: int, lang: str = "uz"):
    # 1. Check cache first for instant sending
    cached = await get_cached_audio(video_id)
    saved = await is_favorite(user_id, video_id)
    kb = get_track_actions_keyboard(video_id, is_saved=saved, lang=lang)

    if cached and cached.get("file_id"):
        file_size_mb = round(cached.get("file_size", 0) / (1024 * 1024), 1) if cached.get("file_size") else ""
        size_line = f"💾 <b>Hajmi:</b> {file_size_mb} MB | 192 kbps\n\n" if file_size_mb else "\n"
        caption = (
            f"🎧 <b>{cached.get('artist', 'Track')} — {cached.get('title', 'Music')}</b>\n\n"
            f"⏱ <b>Davomiyligi:</b> {format_duration(cached.get('duration', 0))}\n"
            f"{size_line}"
            f"🤖 <b>@{BOT_USERNAME}</b> — <i>Eng sara taronalar!</i>"
        )
        await increment_stat("total_downloads")
        await context_msg.answer_audio(
            audio=cached["file_id"],
            caption=caption,
            title=cached.get("title", ""),
            performer=cached.get("artist", ""),
            duration=cached.get("duration", 0),
            reply_markup=kb,
            parse_mode="HTML"
        )
        return

    # 2. Not cached: show downloading status
    status_msg = await context_msg.answer(
        "⚡️ <b>Qo'shiq yuklanmoqda...</b> <i>(Iltimos, kuting)</i>" if lang == "uz" else
        ("⚡️ <b>Трек загружается...</b> <i>(Пожалуйста, подождите)</i>" if lang == "ru" else "⚡️ <b>Downloading track...</b> <i>(Please wait)</i>"),
        parse_mode="HTML"
    )

    info = await download_track_mp3(video_id)
    if not info:
        error_text = (
            "❌ <b>Kechirasiz, musiqani yuklab olishda xatolik yuz berdi.</b>" if lang == "uz" else
            ("❌ <b>Ошибка при загрузке трека.</b>" if lang == "ru" else "❌ <b>Error downloading track.</b>")
        )
        await status_msg.edit_text(error_text, parse_mode="HTML")
        return

    if info.get("error") == "too_long":
        too_long_text = (
            "⚠️ <b>Ushbu fayl davomiyligi juda katta (20 daqiqadan ortiq).</b>\nFaqat qisqaroq musiqa va treklarni yuklab olishingiz mumkin."
            if lang == "uz" else
            ("⚠️ <b>Длительность этого аудио слишком большая (более 20 минут).</b>\nБот скачивает только треки обычной длины."
             if lang == "ru" else "⚠️ <b>Audio is too long (over 20 minutes).</b>\nPlease download standard tracks.")
        )
        await status_msg.edit_text(too_long_text, parse_mode="HTML")
        return

    if not os.path.exists(info["file_path"]):
        await status_msg.edit_text("❌ Xatolik yuz berdi.", parse_mode="HTML")
        return

    try:
        try:
            await status_msg.edit_text(
                "📤 <b>Telegramga yuborilmoqda...</b>" if lang == "uz" else
                ("📤 <b>Отправка в Telegram...</b>" if lang == "ru" else "📤 <b>Sending to Telegram...</b>"),
                parse_mode="HTML"
            )
        except Exception:
            pass

        mp3_file = FSInputFile(info["file_path"])
        file_size_mb = round(info.get("file_size", 0) / (1024 * 1024), 1)
        caption = (
            f"🎧 <b>{info['artist']} — {info['title']}</b>\n\n"
            f"⏱ <b>Davomiyligi:</b> {format_duration(info['duration'])}\n"
            f"💾 <b>Hajmi:</b> {file_size_mb} MB\n\n"
            f"🤖 <b>@{BOT_USERNAME}</b> — <i>Eng sara taronalar!</i>"
        )
        await increment_stat("total_downloads")
        sent_audio = await context_msg.answer_audio(
            audio=mp3_file,
            title=info["title"],
            performer=info["artist"],
            duration=info["duration"],
            caption=caption,
            reply_markup=kb,
            parse_mode="HTML"
        )

        # Save to database cache for instant future deliveries
        file_id = sent_audio.audio.file_id
        await save_audio_cache(
            video_id=video_id,
            title=info["title"],
            artist=info["artist"],
            duration=info["duration"],
            file_id=file_id,
            thumbnail_url=info.get("thumbnail_url", ""),
            file_size=info.get("file_size", 0)
        )
        try:
            await status_msg.delete()
        except Exception:
            pass
    except Exception as e:
        print(f"[Send Audio Error] {e}")
        await status_msg.edit_text("❌ Xatolik yuz berdi.", parse_mode="HTML")
    finally:
        # Delete local temporary mp3 file to save disk space
        if os.path.exists(info["file_path"]):
            try:
                os.remove(info["file_path"])
            except Exception:
                pass

async def handle_media_download(message: types.Message, query: str, user_id: int, lang: str = "uz"):
    media_url = extract_media_url(query) or query

    status_msg = await message.answer(
        "⚡️ <b>Media yuklanmoqda va tahlil qilinmoqda...</b>" if lang == "uz" else
        ("⚡️ <b>Загрузка и обработка медиа...</b>" if lang == "ru" else "⚡️ <b>Downloading and processing media...</b>"),
        parse_mode="HTML"
    )

    media_info = await download_media_from_url(media_url)
    if not media_info or not os.path.exists(media_info.get("video_path", "")):
        fail_text = (
            "⚠️ <b>Ushbu havola orqali mediani yuklab bo'lmadi.</b>\n\n"
            "💡 <b>Maslahat:</b> Instagram yoki TikTok videosini botga to'g'ridan-to'g'ri <b>video shaklida yuboring (forward qiling)</b>! "
            "Bot videoning o'zidan uning musiqasini (MP3) va matnini darhol ajratib beradi! 🎧"
            if lang == "uz" else
            ("⚠️ <b>Не удалось скачать медиа по этой ссылке.</b>\n\n"
             "💡 <b>Совет:</b> Перешлите или отправьте само видео боту! Бот мгновенно извлечет аудио (MP3) и текст прямо из видео! 🎧"
             if lang == "ru" else
             "⚠️ <b>Could not download media from this link.</b>\n\n"
             "💡 <b>Tip:</b> Forward or send the video directly to the bot! The bot will instantly extract the audio (MP3) and caption! 🎧")
        )
        await status_msg.edit_text(fail_text, parse_mode="HTML")
        return

    video_path = media_info["video_path"]
    try:
        raw_caption = media_info.get("caption") or ""
        title = media_info.get("title") or "Media Video"
        author = media_info.get("author") or (f"@{BOT_USERNAME}" if BOT_USERNAME else BOT_NAME)

        # 1. First send the video
        video_caption = ""
        if raw_caption:
            clean_cap = raw_caption[:600].strip()
            video_caption = (
                f"📝 <b>Matn:</b>\n<i>{clean_cap}</i>\n\n"
                if lang == "uz" else
                (f"📝 <b>Текст:</b>\n<i>{clean_cap}</i>\n\n"
                 if lang == "ru" else f"📝 <b>Caption:</b>\n<i>{clean_cap}</i>\n\n")
            )
        video_footer = f"🤖 <b>@{BOT_USERNAME}</b> — <i>Musiqa va Video xizmati</i>"
        full_video_caption = f"{video_caption}{video_footer}"

        try:
            await status_msg.edit_text(
                "📤 <b>Video va audio Telegramga yuborilmoqda...</b>" if lang == "uz" else
                ("📤 <b>Отправка видео и аудио в Telegram...</b>" if lang == "ru" else "📤 <b>Sending video and audio...</b>"),
                parse_mode="HTML"
            )
        except Exception:
            pass

        await message.answer_video(
            video=FSInputFile(video_path),
            caption=full_video_caption,
            parse_mode="HTML"
        )

        # 2. Extract and send MP3 audio
        song_title = raw_caption[:50].strip() if raw_caption else title[:50]
        audio_info = await extract_audio_from_video(
            video_path,
            title=song_title,
            artist=author
        )

        if audio_info and os.path.exists(audio_info["file_path"]):
            song_id = f"med_{uuid.uuid4().hex[:8]}"
            file_size_mb = round(audio_info["file_size"] / (1024 * 1024), 1)

            audio_caption = (
                f"🎧 <b>{audio_info['artist']} — {audio_info['title']}</b>\n\n"
                f"⏱ <b>Davomiyligi:</b> {audio_info['duration_str']}\n"
                f"💾 <b>Hajmi:</b> {file_size_mb} MB | 192 kbps\n\n"
                f"🤖 <b>@{BOT_USERNAME}</b>"
            )

            kb = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(
                    text="❤️ Saqlash" if lang == "uz" else ("❤️ Сохранить" if lang == "ru" else "❤️ Save"),
                    callback_data=f"fav:{song_id}"
                ),
                InlineKeyboardButton(
                    text="↗️ Ulashish" if lang == "uz" else ("↗️ Поделиться" if lang == "ru" else "↗️ Share"),
                    switch_inline_query=song_title
                )
            ]])

            sent_audio = await message.answer_audio(
                audio=FSInputFile(audio_info["file_path"]),
                caption=audio_caption,
                title=audio_info["title"],
                performer=audio_info["artist"],
                duration=audio_info["duration"],
                reply_markup=kb,
                parse_mode="HTML"
            )

            await save_audio_cache(
                video_id=song_id,
                title=audio_info["title"],
                artist=audio_info["artist"],
                duration=audio_info["duration"],
                file_id=sent_audio.audio.file_id,
                file_size=audio_info["file_size"]
            )
            await increment_stat("total_downloads")

            if os.path.exists(audio_info["file_path"]):
                try:
                    os.remove(audio_info["file_path"])
                except Exception:
                    pass

        try:
            await status_msg.delete()
        except Exception:
            pass

    except Exception as e:
        print(f"[Media Process Error] {e}")
        await status_msg.edit_text("❌ Xatolik yuz berdi.", parse_mode="HTML")
    finally:
        if os.path.exists(video_path):
            try:
                os.remove(video_path)
            except Exception:
                pass

# --- Favorites handler (Save / Remove) ---
@router.callback_query(F.data.startswith("fav:"))
async def cb_add_fav(callback: CallbackQuery):
    video_id = callback.data.split(":")[1]
    user_id = callback.from_user.id
    lang = await get_user_language(user_id)

    cached = await get_cached_audio(video_id)
    if cached:
        await add_favorite(
            user_id=user_id,
            video_id=video_id,
            title=cached.get("title", "Track"),
            artist=cached.get("artist", "Artist"),
            file_id=cached.get("file_id", "")
        )
        await callback.answer(
            "❤️ Sevimlilarga qo'shildi!" if lang == "uz" else
            ("❤️ Добавлено в избранное!" if lang == "ru" else "❤️ Added to favorites!")
        )
        await callback.message.edit_reply_markup(
            reply_markup=get_track_actions_keyboard(video_id, is_saved=True, lang=lang)
        )
    else:
        await callback.answer("✅ Saqlandi!")

@router.callback_query(F.data.startswith("unfav:"))
async def cb_del_fav(callback: CallbackQuery):
    video_id = callback.data.split(":")[1]
    user_id = callback.from_user.id
    lang = await get_user_language(user_id)

    await remove_favorite(user_id, video_id)
    await callback.answer(
        "💔 Sevimlilardan o'chirildi!" if lang == "uz" else
        ("💔 Удалено из избранного!" if lang == "ru" else "💔 Removed from favorites!")
    )
    await callback.message.edit_reply_markup(
        reply_markup=get_track_actions_keyboard(video_id, is_saved=False, lang=lang)
    )

# --- Lyrics (Matni) handler ---
@router.callback_query(F.data.startswith("lyr:"))
async def cb_lyrics(callback: CallbackQuery):
    video_id = callback.data.split(":")[1]
    user_id = callback.from_user.id
    lang = await get_user_language(user_id)

    await callback.answer(
        "📜 Matn qidirilmoqda..." if lang == "uz" else
        ("📜 Поиск текста..." if lang == "ru" else "📜 Searching lyrics...")
    )

    cached = await get_cached_audio(video_id)
    title = cached.get("title", "") if cached else ""
    artist = cached.get("artist", "") if cached else ""

    lyrics_data = await get_lyrics(title=title, artist=artist)
    if lyrics_data and lyrics_data.get("lyrics"):
        text = (
            f"📜 <b>{lyrics_data['artist']} — {lyrics_data['title']}</b>\n\n"
            f"{lyrics_data['lyrics'][:3800]}\n\n"
            f"🎧 @{BOT_USERNAME}"
        )
    else:
        text = (
            f"😔 <b>«{artist} - {title}» uchun matn topilmadi.</b>" if lang == "uz" else
            (f"😔 <b>Текст для «{artist} - {title}» не найден.</b>" if lang == "ru" else f"😔 <b>Lyrics not found for «{artist} - {title}».</b>")
        )

    await callback.message.answer(text, parse_mode="HTML")
