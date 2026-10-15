import uuid
from aiogram import Router, F, types
from aiogram.types import CallbackQuery
from database import get_user_language
from keyboards.inline import get_charts_keyboard
from services.charts_service import get_chart_tracks, CHART_CATEGORIES
from handlers.user import SEARCH_CACHE, send_search_page

router = Router()

@router.message(F.text == "🔝 Top Musiqalar")
@router.message(F.text == "🔝 Топ треки")
@router.message(F.text == "🔝 Top Hits")
async def btn_top_charts(message: types.Message):
    lang = await get_user_language(message.from_user.id)
    text = (
        "🔝 <b>O'zingizga ma'qul bo'lgan xitlar to'plamini tanlang:</b>"
        if lang == "uz" else
        ("🔝 <b>Выберите интересующий вас музыкальный чарт:</b>"
         if lang == "ru" else "🔝 <b>Select a top music chart:</b>")
    )
    await message.answer(text, reply_markup=get_charts_keyboard(lang), parse_mode="HTML")

@router.callback_query(F.data.startswith("chart:"))
async def cb_chart_category(callback: CallbackQuery):
    cat_key = callback.data.split(":")[1]
    lang = await get_user_language(callback.from_user.id)
    cat_info = CHART_CATEGORIES.get(cat_key, CHART_CATEGORIES["uzbek"])

    await callback.answer(f"⏳ {cat_info['title']}...")
    loading_msg = await callback.message.answer(
        f"🔥 <b>{cat_info['title']} to'plami yuklanmoqda...</b>",
        parse_mode="HTML"
    )

    results = await get_chart_tracks(cat_key, limit=10)
    if not results:
        await loading_msg.edit_text("😔 Xatolik yuz berdi yoki qo'shiqlar topilmadi.")
        return

    session_id = uuid.uuid4().hex[:10]
    SEARCH_CACHE[session_id] = results
    await send_search_page(loading_msg, session_id, page=0, lang=lang, is_edit=True)
