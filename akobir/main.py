import sys
import asyncio
import logging

# Ensure UTF-8 output for Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from config import BOT_TOKEN, BOT_NAME
from database import init_db
from middlewares.subscription_middleware import SubscriptionMiddleware
from handlers import user, audio, charts, favorites, inline, admin

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("MyMusicBot")

async def set_default_commands(bot: Bot):
    commands = [
        BotCommand(command="start", description="🚀 Botni ishga tushirish"),
        BotCommand(command="top", description="🔝 Top va xit taronalar"),
        BotCommand(command="favorites", description="❤️ Mening musiqalarim"),
        BotCommand(command="settings", description="⚙️ Sozlamalar"),
        BotCommand(command="help", description="ℹ️ Qo'llanma"),
    ]
    try:
        await bot.set_my_commands(commands)
    except Exception as e:
        logger.warning(f"Failed to set bot commands: {e}")

async def main():
    if not BOT_TOKEN or BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        logger.error("=" * 60)
        logger.error("❌ BOT_TOKEN topilmadi!")
        logger.error("Iltimos, .env fayliga Telegram bot tokeningizni kiriting:")
        logger.error("BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz")
        logger.error("=" * 60)
        print("\n[OGOHLANTIRISH] .env fayliga BOT_TOKEN kiriting!\n")
        return

    # Initialize Database
    logger.info("Initializing database...")
    await init_db()

    # Initialize Bot & Dispatcher
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher(storage=MemoryStorage())

    # Register Middlewares
    dp.update.middleware(SubscriptionMiddleware())

    # Register Routers (Order matters)
    dp.include_router(admin.router)
    dp.include_router(charts.router)
    dp.include_router(favorites.router)
    dp.include_router(audio.router)
    dp.include_router(inline.router)
    dp.include_router(user.router)

    # Setup Bot Commands
    await set_default_commands(bot)

    bot_info = await bot.get_me()
    logger.info(f"✅ Bot muvaffaqiyatli ishga tushdi: @{bot_info.username} ({bot_info.first_name})")
    print(f"\n🎧 {BOT_NAME} (@{bot_info.username}) muvaffaqiyatli ishga tushdi!\n")

    # Start Polling
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot to'xtatildi.")
