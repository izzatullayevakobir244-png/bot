from aiogram import Router, F, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from database import get_user_language, get_user_favorites, count_user_favorites
from handlers.user import handle_download

router = Router()

@router.message(F.text == "❤️ Sevimlilar")
@router.message(F.text == "❤️ Избранное")
@router.message(F.text == "❤️ Favorites")
async def btn_favorites(message: types.Message):
    user_id = message.from_user.id
    lang = await get_user_language(user_id)

    total_favs = await count_user_favorites(user_id)
    if total_favs == 0:
        empty_text = (
            "❤️ <b>Sizda hali saqlangan qo'shiqlar yo'q.</b>\n"
            "Qo'shiq yuklab olgach, <b>«❤️ Saqlash»</b> tugmasini bosib shu yerga qo'shishingiz mumkin!"
            if lang == "uz" else
            ("❤️ <b>У вас пока нет сохраненных песен.</b>\n"
             "После скачивания трека нажмите <b>«❤️ Сохранить»</b>, чтобы добавить его сюда!"
             if lang == "ru" else
             "❤️ <b>You have no saved tracks yet.</b>\nTap <b>«❤️ Save»</b> on any track to add it here!")
        )
        await message.answer(empty_text, parse_mode="HTML")
        return

    fav_tracks = await get_user_favorites(user_id, limit=20)

    text_lines = [
        f"❤️ <b>Mening sevimli taronalarim ({total_favs} ta):</b>\n"
        if lang == "uz" else
        (f"❤️ <b>Мои сохраненные треки ({total_favs}):</b>\n"
         if lang == "ru" else f"❤️ <b>My Favorite Tracks ({total_favs}):</b>\n")
    ]

    kb_buttons = []
    for idx, tr in enumerate(fav_tracks, start=1):
        text_lines.append(f"<b>{idx}.</b> {tr['artist']} - {tr['title']}")
        kb_buttons.append([
            InlineKeyboardButton(
                text=f"▶️ {idx}. {tr['artist']} - {tr['title'][:25]}",
                callback_data=f"dl:{tr['video_id']}"
            ),
            InlineKeyboardButton(
                text="❌",
                callback_data=f"fav_rm:{tr['video_id']}"
            )
        ])

    full_text = "\n".join(text_lines)
    await message.answer(
        full_text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_buttons),
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("fav_rm:"))
async def cb_remove_from_favorites(callback: CallbackQuery):
    video_id = callback.data.split(":")[1]
    user_id = callback.from_user.id
    lang = await get_user_language(user_id)

    from database import remove_favorite
    await remove_favorite(user_id, video_id)
    await callback.answer(
        "💔 O'chirildi!" if lang == "uz" else ("💔 Удалено!" if lang == "ru" else "💔 Removed!")
    )

    total_favs = await count_user_favorites(user_id)
    if total_favs == 0:
        empty_text = (
            "❤️ <b>Sizda hali saqlangan qo'shiqlar yo'q.</b>\n"
            "Qo'shiq yuklab olgach, <b>«❤️ Saqlash»</b> tugmasini bosib shu yerga qo'shishingiz mumkin!"
            if lang == "uz" else
            ("❤️ <b>У вас пока нет сохраненных песен.</b>\n"
             "После скачивания трека нажмите <b>«❤️ Сохранить»</b>, чтобы добавить его сюда!"
             if lang == "ru" else
             "❤️ <b>You have no saved tracks yet.</b>\nTap <b>«❤️ Save»</b> on any track to add it here!")
        )
        await callback.message.edit_text(empty_text, parse_mode="HTML")
        return

    fav_tracks = await get_user_favorites(user_id, limit=20)
    text_lines = [
        f"❤️ <b>Mening sevimli taronalarim ({total_favs} ta):</b>\n"
        if lang == "uz" else
        (f"❤️ <b>Мои сохраненные треки ({total_favs}):</b>\n"
         if lang == "ru" else f"❤️ <b>My Favorite Tracks ({total_favs}):</b>\n")
    ]

    kb_buttons = []
    for idx, tr in enumerate(fav_tracks, start=1):
        text_lines.append(f"<b>{idx}.</b> {tr['artist']} - {tr['title']}")
        kb_buttons.append([
            InlineKeyboardButton(
                text=f"▶️ {idx}. {tr['artist']} - {tr['title'][:25]}",
                callback_data=f"dl:{tr['video_id']}"
            ),
            InlineKeyboardButton(
                text="❌",
                callback_data=f"fav_rm:{tr['video_id']}"
            )
        ])

    full_text = "\n".join(text_lines)
    await callback.message.edit_text(
        full_text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_buttons),
        parse_mode="HTML"
    )
