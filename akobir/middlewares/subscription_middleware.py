from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject
from config import ADMINS
from database import get_mandatory_channels, get_user_language
from keyboards.inline import get_subscription_keyboard

class SubscriptionMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        user_id = None
        if isinstance(event, Message):
            user_id = event.from_user.id
            if event.text and event.text.startswith("/start"):
                return await handler(event, data)
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id
            if event.data == "check_sub":
                return await handler(event, data)

        if not user_id:
            return await handler(event, data)

        # Admins always bypass subscription check
        if user_id in ADMINS:
            return await handler(event, data)

        channels = await get_mandatory_channels()
        if not channels:
            return await handler(event, data)

        bot = data["bot"]
        unsubscribed = []

        for ch in channels:
            try:
                ch_raw = str(ch["channel_id"]).strip()
                ch_target = int(ch_raw) if (ch_raw.startswith("-") or ch_raw.isdigit()) else ch_raw
                member = await bot.get_chat_member(chat_id=ch_target, user_id=user_id)
                if member.status not in ["creator", "administrator", "member"]:
                    unsubscribed.append(ch)
            except Exception:
                # If bot cannot check (e.g. not admin in channel), skip to avoid blocking users
                continue

        if unsubscribed:
            lang = await get_user_language(user_id)
            msg_text = (
                "⚠️ <b>Botdan to'liq foydalanish uchun quyidagi homiy kanallarga obuna bo'ling!</b>\n\n"
                "Obuna bo'lgach, <b>«Obunani tekshirish»</b> tugmasini bosing."
            )
            if lang == "ru":
                msg_text = (
                    "⚠️ <b>Для использования бота подпишитесь на каналы ниже!</b>\n\n"
                    "После подписки нажмите кнопку <b>«Проверить подписку»</b>."
                )
            elif lang == "en":
                msg_text = (
                    "⚠️ <b>Please subscribe to the sponsor channels below to use this bot!</b>\n\n"
                    "After subscribing, tap <b>«Check subscription»</b>."
                )

            kb = get_subscription_keyboard(unsubscribed, lang=lang)

            if isinstance(event, Message):
                await event.answer(msg_text, reply_markup=kb, parse_mode="HTML")
            elif isinstance(event, CallbackQuery):
                await event.message.answer(msg_text, reply_markup=kb, parse_mode="HTML")
                await event.answer()
            return

        return await handler(event, data)
