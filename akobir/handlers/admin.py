import asyncio
from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from config import ADMINS
from database import (
    get_bot_stats, get_all_user_ids,
    get_mandatory_channels, add_mandatory_channel, remove_mandatory_channel,
    get_setting, set_setting
)
from services.gemini_service import get_active_gemini_key
from keyboards.inline import get_admin_keyboard

router = Router()

class AdminStates(StatesGroup):
    waiting_broadcast = State()
    waiting_channel_data = State()

def is_admin(user_id: int) -> bool:
    return user_id in ADMINS

@router.message(Command("admin"))
@router.message(F.text.in_(["👨‍💻 Admin Panel", "👨‍💻 Админ панель"]))
async def cmd_admin(message: types.Message):
    if not is_admin(message.from_user.id):
        return

    text = (
        "👑 <b>Boshqaruv paneli (Admin Panel)</b>\n\n"
        "Quyidagi bo'limlardan birini tanlang:"
    )
    await message.answer(text, reply_markup=get_admin_keyboard(), parse_mode="HTML")

# --- Stats Callback ---
@router.callback_query(F.data == "adm:stats")
async def cb_admin_stats(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return

    stats = await get_bot_stats()
    text = (
        "📊 <b>Bot Statistikasi:</b>\n\n"
        f"👥 <b>Jami foydalanuvchilar:</b> {stats.get('total_users', 0):,} ta\n"
        f"🎧 <b>Keshdagi qo'shiqlar:</b> {stats.get('cached_songs', 0):,} ta\n"
        f"🔍 <b>Jami qidiruvlar:</b> {stats.get('total_searches', 0):,} marta\n"
        f"📥 <b>Jami yuklab olingan:</b> {stats.get('total_downloads', 0):,} marta\n"
    )
    await callback.message.edit_text(text, reply_markup=get_admin_keyboard(), parse_mode="HTML")
    await callback.answer()

# --- Broadcast Handlers ---
@router.callback_query(F.data == "adm:broadcast")
async def cb_admin_broadcast(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return

    await state.set_state(AdminStates.waiting_broadcast)
    cancel_kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="❌ Bekor qilish", callback_data="adm:cancel")
    ]])
    await callback.message.edit_text(
        "📢 <b>Barcha foydalanuvchilarga yubormoqchi bo'lgan xabaringizni yuboring:</b>\n"
        "(Matn, rasm, video, audio yoki forward xabar yuborishingiz mumkin)",
        reply_markup=cancel_kb,
        parse_mode="HTML"
    )
    await callback.answer()

@router.message(AdminStates.waiting_broadcast)
async def process_broadcast_message(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    await state.clear()
    status_msg = await message.answer("⏳ <b>Xabar yuborilmoqda...</b>", parse_mode="HTML")

    user_ids = await get_all_user_ids()
    success_count = 0
    fail_count = 0

    for uid in user_ids:
        try:
            await message.copy_to(chat_id=uid)
            success_count += 1
            await asyncio.sleep(0.04) # Telegram rate limits prevention (approx 25 msgs/sec)
        except Exception:
            fail_count += 1

    report = (
        "✅ <b>Xabar tarqatish yakunlandi!</b>\n\n"
        f"📨 <b>Yetkazildi:</b> {success_count} ta foydalanuvchiga\n"
        f"🚫 <b>Yetib bormadi (bloklagan):</b> {fail_count} ta"
    )
    await status_msg.edit_text(report, reply_markup=get_admin_keyboard(), parse_mode="HTML")

# --- Mandatory Channels Management ---
@router.callback_query(F.data == "adm:list_channels")
async def cb_list_channels(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return

    channels = await get_mandatory_channels()
    if not channels:
        await callback.message.edit_text(
            "📋 <b>Hozircha hech qanday homiy kanal belgilanmagan.</b>",
            reply_markup=get_admin_keyboard(),
            parse_mode="HTML"
        )
        return

    text_lines = ["📋 <b>Faol majburiy kanallar:</b>\n"]
    for ch in channels:
        text_lines.append(f"• <b>{ch['channel_title']}</b> ({ch['channel_id']})\n  Link: {ch['channel_url']}")

    await callback.message.edit_text(
        "\n".join(text_lines),
        reply_markup=get_admin_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data == "adm:add_channel")
async def cb_add_channel(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return

    await state.set_state(AdminStates.waiting_channel_data)
    cancel_kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="❌ Bekor qilish", callback_data="adm:cancel")
    ]])
    await callback.message.edit_text(
        "➕ <b>Kanal ma'lumotlarini quyidagi formatda yuboring:</b>\n\n"
        "<code>KANAL_ID|KANAL_NOMI|KANAL_HAVOLASI</code>\n\n"
        "<i>Misol:</i>\n"
        "<code>@mychannel|Mening Kanalim|https://t.me/mychannel</code>\n\n"
        "<i>Eslatma: Bot ushbu kanalda administrator bo'lishi shart!</i>",
        reply_markup=cancel_kb,
        parse_mode="HTML"
    )
    await callback.answer()

@router.message(AdminStates.waiting_channel_data)
async def process_channel_data(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    raw = message.text.strip()
    parts = raw.split("|")
    if len(parts) != 3:
        await message.answer("❌ Noto'g'ri format. Iltimos: <code>KANAL_ID|KANAL_NOMI|KANAL_HAVOLASI</code>", parse_mode="HTML")
        return

    ch_id = parts[0].strip()
    ch_title = parts[1].strip()
    ch_url = parts[2].strip()

    await add_mandatory_channel(ch_id, ch_title, ch_url)
    await state.clear()
    await message.answer(
        f"✅ <b>Kanal muvaffaqiyatli qo'shildi:</b>\n{ch_title} ({ch_id})",
        reply_markup=get_admin_keyboard(),
        parse_mode="HTML"
    )

@router.callback_query(F.data == "adm:del_channel")
async def cb_del_channel_menu(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return

    channels = await get_mandatory_channels()
    if not channels:
        await callback.message.edit_text("📋 Hech qanday kanal yo'q.", reply_markup=get_admin_keyboard())
        return

    kb_buttons = []
    for ch in channels:
        kb_buttons.append([
            InlineKeyboardButton(
                text=f"🗑 {ch['channel_title']}",
                callback_data=f"adm:rm_ch:{ch['channel_id']}"
            )
        ])
    kb_buttons.append([InlineKeyboardButton(text="◀️ Ortga", callback_data="adm:back")])

    await callback.message.edit_text(
        "O'chirmoqchi bo'lgan kanalni tanlang:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_buttons)
    )
    await callback.answer()

@router.callback_query(F.data.startswith("adm:rm_ch:"))
async def cb_delete_specific_channel(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return

    channel_id = callback.data.split("adm:rm_ch:")[1]
    await remove_mandatory_channel(channel_id)
    await callback.answer("✅ Kanal o'chirildi!")
    await cb_del_channel_menu(callback)

# --- Gemini AI Settings ---
@router.callback_query(F.data == "adm:gemini")
async def cb_admin_gemini(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return

    active_key = await get_active_gemini_key()
    if active_key:
        masked_key = active_key[:6] + "..." + active_key[-4:] if len(active_key) > 10 else "***"
        status = f"✅ <b>Faol (Ulangan):</b> <code>{masked_key}</code>"
    else:
        status = "⚠️ <b>Hali o'rnatilmagan</b>"

    text = (
        "🤖 <b>Gemini AI Tizimi Sozlamasi</b>\n\n"
        f"<b>Holati:</b> {status}\n\n"
        "💡 <b>Gemini AI nima beradi?</b>\n"
        "• Foydalanuvchilar 'menga falon ashula kerak' deganida aniq nomini ajratib oladi\n"
        "• Qo'shiq so'zlaridan ('yuragim sezar...') asl qo'shiqni topadi\n"
        "• 'manashu musiqa kerak' deganda tushuntirish so'raydi\n"
        "• Musiqiy savollarga aqlli javob beradi\n\n"
        "📌 <b>Kalitni o'rnatish yoki yangilash:</b>\n"
        "Quyidagi buyruqni botga yuboring:\n"
        "<code>/set_gemini SIZNING_GEMINI_API_KALITINGIZ</code>\n\n"
        "<i>(Yoki loyihaning <code>.env</code> fayliga <code>GEMINI_API_KEY=...</code> qo'shishingiz mumkin)</i>"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="◀️ Ortga", callback_data="adm:back")
    ]])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()

@router.message(Command("set_gemini"))
async def cmd_set_gemini(message: types.Message):
    if not is_admin(message.from_user.id):
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        await message.answer(
            "⚠️ <b>Iltimos, API kalitingizni kiriting!</b>\n\n"
            "Format: <code>/set_gemini AIzaSy...</code>",
            parse_mode="HTML"
        )
        return

    new_key = parts[1].strip()
    await set_setting("gemini_api_key", new_key)
    masked = new_key[:6] + "..." + new_key[-4:] if len(new_key) > 10 else "***"
    await message.answer(
        f"✅ <b>Gemini API kaliti muvaffaqiyatli saqlandi!</b>\n\n"
        f"🔑 Kalit: <code>{masked}</code>\n\n"
        "Endi bot barcha matnli so'rovlar, so'zlar va noaniq xabarlarni Gemini AI orqali aniqlab, eng to'g'ri musiqalarni topib beradi! 🎧",
        parse_mode="HTML"
    )

@router.callback_query(F.data == "adm:cancel")
@router.callback_query(F.data == "adm:back")
async def cb_admin_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "👑 <b>Boshqaruv paneli (Admin Panel)</b>",
        reply_markup=get_admin_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()

