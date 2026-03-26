import os

# ---------- Telethon User Session ----------
API_ID = int(os.environ.get("API_ID", 123456))
API_HASH = os.environ.get("API_HASH", "your_api_hash")
PHONE_NUMBER = os.environ.get("PHONE_NUMBER", "+1234567890")

# ---------- Bot ----------
BOT_TOKEN = os.environ.get("BOT_TOKEN", "your_bot_token")

# ---------- Security ----------
ALLOWED_USER_IDS = [int(x) for x in os.environ.get("ALLOWED_USER_IDS", "123456789").split(",")]

# ---------- Database ----------
DB_PATH = os.environ.get("DB_PATH", "data/osint.db")

# ---------- Default Settings ----------
DEFAULT_FORWARD_MODE = "copy"
DEFAULT_CONTENT_TYPES = ["text", "photo", "video", "document", "audio"]

# ---------- Performance ----------
MAX_CONCURRENT_TASKS = 10
QUEUE_MAX_SIZE = 1000

TRIAGE_WORKERS = 2
ALERT_WORKERS = 1
CORRELATION_WORKERS = 1
DEEP_ANALYSIS_WORKERS = 0

# ---------- Categories ----------
CATEGORIES = [
    "عسكري", "أمني", "سياسي", "اقتصادي", "إعلامي", "دبلوماسي", "محلي", "دولي"
]

# ---------- AI Settings ----------
AI_ENABLED = True
AI_FAST_MODE = True
AI_IMPORTANCE_THRESHOLD = 0.7
AI_URGENCY_THRESHOLD = 0.7
AI_CONFIDENCE_THRESHOLD = 0.6
AI_CORRELATION_WINDOW = 120
AI_CORRELATION_SIMILARITY = 0.8
DEEP_ANALYSIS_ENABLED = False

# ---------- Source Scoring ----------
DEFAULT_TRUST_SCORE = 0.5
DEFAULT_SPEED_SCORE = 0.5
DEFAULT_PRIORITY_SCORE = 0.5
