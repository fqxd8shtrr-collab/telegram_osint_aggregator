import os

# ---------- Telethon User Session ----------
API_ID = 123456  # Replace with your API ID
API_HASH = "your_api_hash"  # Replace
PHONE_NUMBER = "+1234567890"  # Replace

# ---------- Bot ----------
BOT_TOKEN = "your_bot_token"  # Replace

# ---------- Security ----------
ALLOWED_USER_IDS = [123456789]  # Replace with your Telegram user ID(s)

# ---------- Database ----------
DB_PATH = "data/osint.db"

# ---------- Default Settings ----------
DEFAULT_FORWARD_MODE = "copy"  # "forward" or "copy"
DEFAULT_PRIMARY_DESTINATION = None
DEFAULT_BACKUP_DESTINATION = None
DEFAULT_ALERT_DESTINATION = None
DEFAULT_NORMAL_FEED_DESTINATION = None
DEFAULT_PRIORITY_FEED_DESTINATION = None
DEFAULT_CRITICAL_ALERT_DESTINATION = None

DEFAULT_CONTENT_TYPES = ["text", "photo", "video", "document", "audio"]

# ---------- Performance ----------
MAX_CONCURRENT_TASKS = 10
QUEUE_MAX_SIZE = 1000

# Worker pools
TRIAGE_WORKERS = 2
ALERT_WORKERS = 1
CORRELATION_WORKERS = 1
DEEP_ANALYSIS_WORKERS = 0  # 0 = disabled

# ---------- Categories ----------
CATEGORIES = [
    "عسكري", "أمني", "سياسي", "اقتصادي", "إعلامي", "دبلوماسي", "محلي", "دولي"
]

# ---------- Priority ----------
PRIORITY_LEVELS = {"high": 1, "normal": 2, "low": 3}

# ---------- AI Settings ----------
AI_ENABLED = True
AI_FAST_MODE = True  # If True, uses keyword/pattern triage; if False, uses model (slower)
AI_IMPORTANCE_THRESHOLD = 0.7
AI_URGENCY_THRESHOLD = 0.7
AI_CONFIDENCE_THRESHOLD = 0.6

# Correlation
AI_CORRELATION_WINDOW = 120  # seconds
AI_CORRELATION_SIMILARITY = 0.8

# Deep Analysis (optional)
DEEP_ANALYSIS_ENABLED = False

# ---------- Source Scoring ----------
DEFAULT_TRUST_SCORE = 0.5
DEFAULT_SPEED_SCORE = 0.5
DEFAULT_PRIORITY_SCORE = 0.5
