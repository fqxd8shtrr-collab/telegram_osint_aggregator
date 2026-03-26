import os

# -------------------- Telethon --------------------
API_ID = int(os.environ.get("API_ID", 123456))
API_HASH = os.environ.get("API_HASH", "your_api_hash")
PHONE_NUMBER = os.environ.get("PHONE_NUMBER", "+1234567890")

# -------------------- Bot --------------------
BOT_TOKEN = os.environ.get("BOT_TOKEN", "your_bot_token")

# -------------------- Security --------------------
ALLOWED_USER_IDS = [int(x) for x in os.environ.get("ALLOWED_USER_IDS", "123456789").split(",")]

# -------------------- Database --------------------
DB_PATH = os.environ.get("DB_PATH", "data/osint.db")  # SQLite file path
# Use PostgreSQL if needed: DATABASE_URL = os.environ.get("DATABASE_URL")

# -------------------- Performance --------------------
MAX_QUEUE_SIZE = 2000
TRIAGE_WORKERS = 2
ALERT_WORKERS = 1
CORRELATION_WORKERS = 1
DEEP_ANALYSIS_WORKERS = 0  # 0 = disabled

# -------------------- AI Settings --------------------
# Fast mode: keyword/pattern-based triage (milliseconds)
AI_FAST_MODE = True
# Importance/urgency thresholds for alerting
IMPORTANCE_THRESHOLD = 0.7
URGENCY_THRESHOLD = 0.7
CONFIDENCE_THRESHOLD = 0.6

# -------------------- Correlation --------------------
CORRELATION_WINDOW = 120  # seconds
SIMILARITY_THRESHOLD = 0.8

# -------------------- Categories --------------------
CATEGORIES = ["عسكري", "سياسي", "أمني", "اقتصادي", "إعلامي", "دبلوماسي", "محلي", "دولي"]
