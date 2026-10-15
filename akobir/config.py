import os
from pathlib import Path
from dotenv import load_dotenv
import imageio_ffmpeg

# Load environment variables from .env file
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent

# Bot Token (User will provide or fill in .env)
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

# Admin IDs (comma separated integers in .env, e.g. "12345678,87654321")
ADMIN_RAW = os.getenv("ADMINS", "")
ADMINS = [int(x.strip()) for x in ADMIN_RAW.split(",") if x.strip().isdigit()]

# Database path
DB_PATH = os.getenv("DB_PATH", str(BASE_DIR / "bot.db"))

# Downloads & Temp directories
TEMP_DIR = BASE_DIR / "downloads"
TEMP_DIR.mkdir(parents=True, exist_ok=True)

# FFmpeg path from imageio-ffmpeg
try:
    FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()
except Exception:
    FFMPEG_PATH = "ffmpeg"

# Bot Information
BOT_NAME = os.getenv("BOT_NAME", "MyMusic Bot")
BOT_USERNAME = os.getenv("BOT_USERNAME", "MyMusic_bot")
SUPPORT_USERNAME = os.getenv("SUPPORT_USERNAME", "")

# Gemini AI API Key for smart music understanding and lyrics recognition
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
