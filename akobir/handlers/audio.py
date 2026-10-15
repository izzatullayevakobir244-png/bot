import os
import uuid
from aiogram import Router, F, types
from aiogram.types import FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton

from config import TEMP_DIR, BOT_NAME, BOT_USERNAME
from database import get_user_language, save_audio_cache, increment_stat
from services.voice_service import recognize_voice_query
from services.music_service import search_tracks
from services.gemini_service import analyze_music_request
from services.media_service import extract_audio_from_video
from handlers.user import SEARCH_CACHE, send_search_page

router = Router()

@router.message(F.voice | F.video_note)
async def handle_voice_message(message: types.Message):
    user_id = message.from_user.id
    lang = await get_user_language(user_id)

    status_msg = await message.answer(
        "🎧 <b>Ovoz tahlil qilinmoqda va qidirilmoqda...</b>" if lang == "uz" else
        ("🎧 <b>Голос обрабатывается и ищется...</b>" if lang == "ru" else "🎧 <b>Processing voice and searching...</b>"),
        parse_mode="HTML"
    )

    bot = message.bot
    file_id = message.voice.file_id if message.voice else message.video_note.file_id
    file_info = await bot.get_file(file_id)

    temp_ext = ".ogg" if message.voice else ".mp4"
    temp_file = str(TEMP_DIR / f"voice_{uuid.uuid4().hex[:8]}{temp_ext}")

    try:
        await bot.download_file(file_info.file_path, temp_file)

        # Transcribe/recognize voice query
        query_text = await recognize_voice_query(temp_file)
        if not query_text:
            fail_text = (
                "😔 <b>Ovozni aniqlab bo'lmadi.</b>\nIltimos, aniqroq gapiring yoki qo'shiq nomini yozing."
                if lang == "uz" else
                ("😔 <b>Не удалось распознать голос.</b>\nПопробуйте сказать четче или напишите текстом."
                 if lang == "ru" else "😔 <b>Could not recognize voice.</b>\nPlease try speaking clearer or write text.")
            )
            await status_msg.edit_text(fail_text, parse_mode="HTML")
            return

        recognized_header = (
            f"🎤 <b>Ovozdan aniqlandi:</b> <i>«{query_text}»</i>\n🔎 Qidirilmoqda..."
            if lang == "uz" else
            (f"🎤 <b>Распознано:</b> <i>«{query_text}»</i>\n🔎 Поиск..."
             if lang == "ru" else f"🎤 <b>Recognized:</b> <i>«{query_text}»</i>\n🔎 Searching...")
        )
        await status_msg.edit_text(recognized_header, parse_mode="HTML")

        # Analyze recognized voice query with AI
        analysis = await analyze_music_request(query_text)
        action = analysis.get("action", "search")
        if action == "need_info":
            await status_msg.edit_text(analysis.get("message", "Qaysi qo'shiq kerak?"), parse_mode="HTML")
            return

        target_q = analysis.get("clean_query") or query_text
        explanation = analysis.get("explanation")
        if explanation:
            header_text = f"🎤 <b>Ovozdan aniqlandi:</b> <i>«{query_text}»</i>\n💡 <i>{explanation}</i>\n🔎 Qidirilmoqda..."
            await status_msg.edit_text(header_text, parse_mode="HTML")

        # Run search with cleaned target text
        results = await search_tracks(target_q, limit=10)
        if not results and analysis.get("title") and analysis.get("title") != target_q:
            results = await search_tracks(analysis["title"], limit=10)

        if not results:
            not_found = (
                f"😔 <b>«{target_q}» bo'yicha qo'shiq topilmadi.</b>"
                if lang == "uz" else
                (f"😔 <b>По запросу «{target_q}» ничего не найдено.</b>"
                 if lang == "ru" else f"😔 <b>No tracks found for «{target_q}».</b>")
            )
            await status_msg.edit_text(not_found, parse_mode="HTML")
            return

        session_id = uuid.uuid4().hex[:10]
        SEARCH_CACHE[session_id] = results
        await send_search_page(status_msg, session_id, page=0, lang=lang, is_edit=True)

    except Exception as e:
        print(f"[Voice Handler Error] {e}")
        await status_msg.edit_text("❌ Xatolik yuz berdi.", parse_mode="HTML")
    finally:
        if os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except Exception:
                pass

@router.message(F.audio)
async def handle_audio_message(message: types.Message):
    user_id = message.from_user.id
    lang = await get_user_language(user_id)
    audio = message.audio

    search_query = ""
    if audio.performer and audio.title:
        search_query = f"{audio.performer} {audio.title}"
    elif audio.title:
        search_query = audio.title
    elif audio.file_name:
        search_query = audio.file_name.rsplit(".", 1)[0]

    if not search_query:
        await message.answer("🎵 Musiqa nomi aniqlanmadi.")
        return

    searching_msg = await message.answer(
        f"🔎 <b>«{search_query}» qidirilmoqda...</b>",
        parse_mode="HTML"
    )

    results = await search_tracks(search_query, limit=10)
    if not results:
        await searching_msg.edit_text(f"😔 «{search_query}» topilmadi.")
        return

    session_id = uuid.uuid4().hex[:10]
    SEARCH_CACHE[session_id] = results
    await send_search_page(searching_msg, session_id, page=0, lang=lang, is_edit=True)

@router.message(F.video)
async def handle_video_message(message: types.Message):
    user_id = message.from_user.id
    lang = await get_user_language(user_id)
    video = message.video

    status_msg = await message.answer(
        "⚡️ <b>Videodan musiqa va matn ajratib olinmoqda...</b>" if lang == "uz" else
        ("⚡️ <b>Извлечение музыки и текста из видео...</b>" if lang == "ru" else "⚡️ <b>Extracting audio and caption from video...</b>"),
        parse_mode="HTML"
    )

    bot = message.bot
    video_id = f"vid_{uuid.uuid4().hex[:8]}"
    temp_video = str(TEMP_DIR / f"input_{video_id}.mp4")

    try:
        file_info = await bot.get_file(video.file_id)
        await bot.download_file(file_info.file_path, temp_video)

        # Caption from message
        raw_caption = message.caption or ""
        song_title = raw_caption[:50].strip() if raw_caption else "Video Musiqasi"

        audio_info = await extract_audio_from_video(
            temp_video,
            title=song_title,
            artist=f"@{BOT_USERNAME}" if BOT_USERNAME else BOT_NAME
        )

        if not audio_info or not os.path.exists(audio_info["file_path"]):
            await status_msg.edit_text(
                "❌ <b>Videodan audio ajratishda xatolik yuz berdi.</b>" if lang == "uz" else
                ("❌ <b>Не удалось извлечь аудио из видео.</b>" if lang == "ru" else "❌ <b>Failed to extract audio from video.</b>"),
                parse_mode="HTML"
            )
            return

        file_size_mb = round(audio_info["file_size"] / (1024 * 1024), 1)

        caption_text = ""
        if raw_caption:
            caption_text = (
                f"📝 <b>Video matni:</b>\n<i>{raw_caption[:400]}</i>\n\n"
                if lang == "uz" else
                (f"📝 <b>Текст видео:</b>\n<i>{raw_caption[:400]}</i>\n\n"
                 if lang == "ru" else f"📝 <b>Video caption:</b>\n<i>{raw_caption[:400]}</i>\n\n")
            )

        caption_block = (
            f"🎬 <b>Videodan musiqa muvaffaqiyatli ajratib olindi!</b>\n\n"
            f"{caption_text}"
            f"⏱ <b>Davomiyligi:</b> {audio_info['duration_str']}\n"
            f"💾 <b>Hajmi:</b> {file_size_mb} MB | 192 kbps\n\n"
            f"🤖 <b>@{BOT_USERNAME}</b> — <i>Musiqa va Video xizmati</i>"
            if lang == "uz" else
            (f"🎬 <b>Музыка успешно извлечена из видео!</b>\n\n"
             f"{caption_text}"
             f"⏱ <b>Длительность:</b> {audio_info['duration_str']}\n"
             f"💾 <b>Размер:</b> {file_size_mb} MB | 192 kbps\n\n"
             f"🤖 <b>@{BOT_USERNAME}</b>"
             if lang == "ru" else
             f"🎬 <b>Audio successfully extracted from video!</b>\n\n"
             f"{caption_text}"
             f"⏱ <b>Duration:</b> {audio_info['duration_str']}\n"
             f"💾 <b>Size:</b> {file_size_mb} MB | 192 kbps\n\n"
             f"🤖 <b>@{BOT_USERNAME}</b>")
        )

        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(
                text="❤️ Saqlash" if lang == "uz" else ("❤️ Сохранить" if lang == "ru" else "❤️ Save"),
                callback_data=f"fav:{video_id}"
            ),
            InlineKeyboardButton(
                text="↗️ Ulashish" if lang == "uz" else ("↗️ Поделиться" if lang == "ru" else "↗️ Share"),
                switch_inline_query=song_title
            )
        ]])

        sent_audio = await message.answer_audio(
            audio=FSInputFile(audio_info["file_path"]),
            caption=caption_block,
            title=song_title,
            performer=f"@{BOT_USERNAME}" if BOT_USERNAME else BOT_NAME,
            duration=audio_info["duration"],
            reply_markup=kb,
            parse_mode="HTML"
        )

        # Cache in database so favorites work
        await save_audio_cache(
            video_id=video_id,
            title=song_title,
            artist=f"@{BOT_USERNAME}" if BOT_USERNAME else BOT_NAME,
            duration=audio_info["duration"],
            file_id=sent_audio.audio.file_id,
            file_size=audio_info["file_size"]
        )
        await increment_stat("total_downloads")

        try:
            await status_msg.delete()
        except Exception:
            pass

        # Clean up files
        if os.path.exists(audio_info["file_path"]):
            os.remove(audio_info["file_path"])

    except Exception as e:
        print(f"[Video Handler Error] {e}")
        await status_msg.edit_text("❌ Xatolik yuz berdi.", parse_mode="HTML")
    finally:
        if os.path.exists(temp_video):
            try:
                os.remove(temp_video)
            except Exception:
                pass
