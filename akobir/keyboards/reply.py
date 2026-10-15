from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from config import ADMINS

def get_main_keyboard(user_id: int, lang: str = "uz") -> ReplyKeyboardMarkup:
    is_admin = user_id in ADMINS

    if lang == "ru":
        btn_search = KeyboardButton(text="🔍 Поиск музыки")
        btn_top = KeyboardButton(text="🔝 Топ треки")
        btn_fav = KeyboardButton(text="❤️ Избранное")
        btn_settings = KeyboardButton(text="⚙️ Настройки")
        btn_about = KeyboardButton(text="ℹ️ О боте")
        btn_admin = KeyboardButton(text="👨‍💻 Админ панель")
    elif lang == "en":
        btn_search = KeyboardButton(text="🔍 Search Music")
        btn_top = KeyboardButton(text="🔝 Top Hits")
        btn_fav = KeyboardButton(text="❤️ Favorites")
        btn_settings = KeyboardButton(text="⚙️ Settings")
        btn_about = KeyboardButton(text="ℹ️ About Bot")
        btn_admin = KeyboardButton(text="👨‍💻 Admin Panel")
    else: # uz
        btn_search = KeyboardButton(text="🔍 Musiqa qidirish")
        btn_top = KeyboardButton(text="🔝 Top Musiqalar")
        btn_fav = KeyboardButton(text="❤️ Sevimlilar")
        btn_settings = KeyboardButton(text="⚙️ Sozlamalar")
        btn_about = KeyboardButton(text="ℹ️ Bot haqida")
        btn_admin = KeyboardButton(text="👨‍💻 Admin Panel")

    keyboard = [
        [btn_search, btn_top],
        [btn_fav, btn_settings],
        [btn_about]
    ]

    if is_admin:
        keyboard.append([btn_admin])

    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True
    )

def get_cancel_keyboard(lang: str = "uz") -> ReplyKeyboardMarkup:
    btn_text = "❌ Bekor qilish"
    if lang == "ru":
        btn_text = "❌ Отмена"
    elif lang == "en":
        btn_text = "❌ Cancel"

    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=btn_text)]],
        resize_keyboard=True
    )
