import os
from dotenv import load_dotenv

load_dotenv()

# Telegram credentials
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
SESSION_STRING = os.getenv("SESSION_STRING", "")  # for Telethon
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# Database
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///data/osint.db")

# Allowed admin user IDs (comma separated)
ALLOWED_USERS = [int(x.strip()) for x in os.getenv("ALLOWED_USERS", "").split(",") if x.strip()]

# AI models settings
FAST_AI_MODEL = os.getenv("FAST_AI_MODEL", "distilbert-base-uncased")  # fast triage
DEEP_AI_MODEL = os.getenv("DEEP_AI_MODEL", "gpt-3.5-turbo")           # deep analysis

# Translation API
TRANSLATION_API = os.getenv("TRANSLATION_API", "google")  # 'google' or 'deepl'
GOOGLE_TRANSLATE_API_KEY = os.getenv("GOOGLE_TRANSLATE_API_KEY", "")
DEEPL_API_KEY = os.getenv("DEEPL_API_KEY", "")

# Worker settings
MAX_WORKERS = int(os.getenv("MAX_WORKERS", "5"))
QUEUE_SIZE = int(os.getenv("QUEUE_SIZE", "1000"))

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Health check interval (seconds)
HEALTH_INTERVAL = int(os.getenv("HEALTH_INTERVAL", "60"))
