from typing import List, Dict, Any
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import BOT_USERNAME

EMOJI_NUMS = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]

def get_search_results_keyboard(
    results: List[Dict[str, Any]],
    current_page: int,
    total_pages: int,
    search_session_id: str
) -> InlineKeyboardMarkup:
    """
    Creates Tarona-style emoji numbered download buttons plus pagination controls and close button.
    """
    keyboard = []

    # Numbered buttons: 1️⃣ .. 5️⃣
    num_buttons = []
    for idx, item in enumerate(results, start=1):
        vid_id = item['id']
        btn_text = EMOJI_NUMS[idx - 1] if idx <= len(EMOJI_NUMS) else str(idx)
        num_buttons.append(
            InlineKeyboardButton(
                text=btn_text,
                callback_data=f"dl:{vid_id}"
            )
        )

    # Put buttons in a single row of 5
    if num_buttons:
        keyboard.append(num_buttons[:5])

    # Pagination buttons row
    nav_buttons = []
    if current_page > 0:
        nav_buttons.append(
            InlineKeyboardButton(
                text="⬅️ Oldingi",
                callback_data=f"page:{search_session_id}:{current_page - 1}"
            )
        )

    if total_pages > 1:
        nav_buttons.append(
            InlineKeyboardButton(
                text=f"{current_page + 1} / {total_pages}",
                callback_data="noop"
            )
        )

    if current_page < total_pages - 1:
        nav_buttons.append(
            InlineKeyboardButton(
                text="Keyingi ➡️",
                callback_data=f"page:{search_session_id}:{current_page + 1}"
            )
        )

    if nav_buttons:
        keyboard.append(nav_buttons)

    # Close button row
    keyboard.append([
        InlineKeyboardButton(text="❌ Natijalarni yopish", callback_data="close_search")
    ])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_track_actions_keyboard(video_id: str, is_saved: bool = False, lang: str = "uz") -> InlineKeyboardMarkup:
    """
    Inline keyboard sent with each audio track:
    - Save / Remove from Favorites
    - Lyrics (Matni)
    - Share with friends (Ulashish)
    """
    fav_text = "💔 Sevimlilardan o'chirish" if is_saved else "❤️ Saqlash"
    lyrics_text = "📜 Matni"
    share_text = "↗️ Do'stlarga ulashish"

    if lang == "ru":
        fav_text = "💔 Удалить" if is_saved else "❤️ Сохранить"
        lyrics_text = "📜 Текст песни"
        share_text = "↗️ Поделиться"
    elif lang == "en":
        fav_text = "💔 Remove" if is_saved else "❤️ Save"
        lyrics_text = "📜 Lyrics"
        share_text = "↗️ Share"

    action = "unfav" if is_saved else "fav"

    keyboard = [
        [
            InlineKeyboardButton(text=fav_text, callback_data=f"{action}:{video_id}"),
            InlineKeyboardButton(text=lyrics_text, callback_data=f"lyr:{video_id}"),
        ],
        [
            InlineKeyboardButton(
                text=share_text,
                switch_inline_query=video_id
            )
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_charts_keyboard(lang: str = "uz") -> InlineKeyboardMarkup:
    """
    Inline keyboard for choosing top music chart.
    """
    buttons = [
        [InlineKeyboardButton(text="🇺🇿 O'zbek xitlari", callback_data="chart:uzbek")],
        [InlineKeyboardButton(text="🇷🇺 Rus xitlari", callback_data="chart:russian")],
        [InlineKeyboardButton(text="🌍 Jahon xitlari", callback_data="chart:global")],
        [InlineKeyboardButton(text="🆕 Yangi taronalar", callback_data="chart:fresh")],
        [InlineKeyboardButton(text="🔥 TikTok & Remix", callback_data="chart:tiktok")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_subscription_keyboard(channels: List[Dict[str, Any]], lang: str = "uz") -> InlineKeyboardMarkup:
    """
    Keyboard shown to users when forced channel subscription is required.
    """
    keyboard = []
    for ch in channels:
        keyboard.append([
            InlineKeyboardButton(
                text=f"📢 {ch['channel_title']}",
                url=ch['channel_url']
            )
        ])

    check_text = "✅ Obunani tekshirish"
    if lang == "ru":
        check_text = "✅ Проверить подписку"
    elif lang == "en":
        check_text = "✅ Check subscription"

    keyboard.append([
        InlineKeyboardButton(text=check_text, callback_data="check_sub")
    ])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_settings_keyboard(current_lang: str = "uz") -> InlineKeyboardMarkup:
    """
    Keyboard for selecting bot language.
    """
    uz_check = " ✅" if current_lang == "uz" else ""
    ru_check = " ✅" if current_lang == "ru" else ""
    en_check = " ✅" if current_lang == "en" else ""

    keyboard = [
        [
            InlineKeyboardButton(text=f"🇺🇿 O'zbekcha{uz_check}", callback_data="setlang:uz"),
            InlineKeyboardButton(text=f"🇷🇺 Русский{ru_check}", callback_data="setlang:ru"),
            InlineKeyboardButton(text=f"🇬🇧 English{en_check}", callback_data="setlang:en"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_admin_keyboard() -> InlineKeyboardMarkup:
    """
    Admin control panel buttons.
    """
    keyboard = [
        [
            InlineKeyboardButton(text="📊 Statistika", callback_data="adm:stats"),
            InlineKeyboardButton(text="📢 Xabar yuborish", callback_data="adm:broadcast")
        ],
        [
            InlineKeyboardButton(text="🤖 Gemini AI Sozlamasi", callback_data="adm:gemini"),
            InlineKeyboardButton(text="📋 Kanallar ro'yxati", callback_data="adm:list_channels")
        ],
        [
            InlineKeyboardButton(text="➕ Kanal qo'shish", callback_data="adm:add_channel"),
            InlineKeyboardButton(text="➖ Kanal o'chirish", callback_data="adm:del_channel")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

