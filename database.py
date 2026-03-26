import sqlite3
import aiosqlite
import json
import datetime
import os
from typing import List, Dict, Any, Optional, Tuple
import config

# Ensure data directory exists
os.makedirs(os.path.dirname(config.DB_PATH) or '.', exist_ok=True)

# -------------------- Initialization --------------------
def init_sync_db():
    """Create tables synchronously (run once at startup)."""
    conn = sqlite3.connect(config.DB_PATH)
    c = conn.cursor()

    # Channels
    c.execute('''
        CREATE TABLE IF NOT EXISTS channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id INTEGER NOT NULL UNIQUE,
            username TEXT,
            title TEXT,
            label TEXT,
            category TEXT,
            enabled INTEGER DEFAULT 1,
            priority INTEGER DEFAULT 0,          -- 0=normal, 1=high
            trust_score REAL DEFAULT 0.5,
            speed_score REAL DEFAULT 0.5,
            language TEXT,
            region TEXT
        )
    ''')

    # Messages (forwarded)
    c.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id INTEGER NOT NULL,
            message_id INTEGER NOT NULL,
            content_hash TEXT,
            normalized_text TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(channel_id, message_id)
        )
    ''')

    # AI evaluations
    c.execute('''
        CREATE TABLE IF NOT EXISTS evaluations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id INTEGER NOT NULL,
            channel_id INTEGER NOT NULL,
            importance REAL,
            urgency REAL,
            confidence REAL,
            event_type TEXT,
            evaluated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(message_id, channel_id) REFERENCES messages(message_id, channel_id)
        )
    ''')

    # Event clusters
    c.execute('''
        CREATE TABLE IF NOT EXISTS clusters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cluster_hash TEXT UNIQUE,
            event_type TEXT,
            importance REAL,
            urgency REAL,
            confidence REAL,
            first_seen TIMESTAMP,
            last_seen TIMESTAMP,
            message_count INTEGER,
            channels TEXT,          -- JSON list of channel ids
            status TEXT DEFAULT 'new'   -- new, under_review, confirmed, published, rejected
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS cluster_messages (
            cluster_id INTEGER,
            message_id INTEGER,
            channel_id INTEGER,
            FOREIGN KEY(cluster_id) REFERENCES clusters(id),
            FOREIGN KEY(message_id, channel_id) REFERENCES messages(message_id, channel_id)
        )
    ''')

    # Team members
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            role TEXT NOT NULL,   -- admin, analyst, editor, monitor
            desk TEXT,            -- category assigned
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Assignments
    c.execute('''
        CREATE TABLE IF NOT EXISTS assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cluster_id INTEGER,
            assigned_to INTEGER,
            assigned_by INTEGER,
            status TEXT DEFAULT 'new',
            comment TEXT,
            assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(cluster_id) REFERENCES clusters(id),
            FOREIGN KEY(assigned_to) REFERENCES users(user_id),
            FOREIGN KEY(assigned_by) REFERENCES users(user_id)
        )
    ''')

    # Comments
    c.execute('''
        CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cluster_id INTEGER,
            user_id INTEGER,
            comment TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(cluster_id) REFERENCES clusters(id),
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        )
    ''')

    # Health metrics
    c.execute('''
        CREATE TABLE IF NOT EXISTS health_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            metric_name TEXT,
            metric_value REAL
        )
    ''')

    # Bot state
    c.execute('''
        CREATE TABLE IF NOT EXISTS bot_state (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    # Default state
    default_state = {
        'is_running': '0',
        'last_error': '',
        'last_activity': '',
        'total_forwarded': '0',
        'total_alerts': '0',
        'start_time': '',
        'ai_fast_mode': str(int(config.AI_FAST_MODE)),
        'importance_threshold': str(config.IMPORTANCE_THRESHOLD),
        'urgency_threshold': str(config.URGENCY_THRESHOLD),
        'confidence_threshold': str(config.CONFIDENCE_THRESHOLD),
        'correlation_window': str(config.CORRELATION_WINDOW)
    }
    for key, val in default_state.items():
        c.execute("INSERT OR IGNORE INTO bot_state (key, value) VALUES (?, ?)", (key, val))

    conn.commit()
    conn.close()

# -------------------- Async helpers --------------------
async def execute(query: str, params: tuple = ()):
    async with aiosqlite.connect(config.DB_PATH) as db:
        return await db.execute(query, params)

async def fetch_one(query: str, params: tuple = ()):
    async with aiosqlite.connect(config.DB_PATH) as db:
        cursor = await db.execute(query, params)
        return await cursor.fetchone()

async def fetch_all(query: str, params: tuple = ()):
    async with aiosqlite.connect(config.DB_PATH) as db:
        cursor = await db.execute(query, params)
        return await cursor.fetchall()

# -------------------- Channels --------------------
async def add_channel(channel_id: int, username: str = None, title: str = None, label: str = None, category: str = None,
                      trust_score: float = 0.5, speed_score: float = 0.5) -> bool:
    async with aiosqlite.connect(config.DB_PATH) as db:
        try:
            await db.execute(
                "INSERT INTO channels (channel_id, username, title, label, category, trust_score, speed_score) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (channel_id, username, title, label, category, trust_score, speed_score)
            )
            await db.commit()
            return True
        except sqlite3.IntegrityError:
            return False

async def get_all_channels() -> List[Dict]:
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM channels") as cur:
            rows = await cur.fetchall()
            return [dict(row) for row in rows]

async def get_channel(channel_id: int) -> Optional[Dict]:
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM channels WHERE channel_id = ?", (channel_id,)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None

async def update_channel_field(channel_id: int, field: str, value):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(f"UPDATE channels SET {field} = ? WHERE channel_id = ?", (value, channel_id))
        await db.commit()

async def toggle_channel_enabled(channel_id: int, enabled: bool):
    await update_channel_field(channel_id, "enabled", 1 if enabled else 0)

async def update_channel_label(channel_id: int, label: str):
    await update_channel_field(channel_id, "label", label)

async def update_channel_category(channel_id: int, category: str):
    await update_channel_field(channel_id, "category", category)

async def update_channel_trust(channel_id: int, trust: float):
    await update_channel_field(channel_id, "trust_score", trust)

# -------------------- Messages --------------------
async def is_message_processed(channel_id: int, message_id: int) -> bool:
    async with aiosqlite.connect(config.DB_PATH) as db:
        async with db.execute("SELECT 1 FROM messages WHERE channel_id = ? AND message_id = ?", (channel_id, message_id)) as cur:
            return await cur.fetchone() is not None

async def save_message(channel_id: int, message_id: int, content_hash: str, normalized_text: str):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            "INSERT INTO messages (channel_id, message_id, content_hash, normalized_text) VALUES (?, ?, ?, ?)",
            (channel_id, message_id, content_hash, normalized_text)
        )
        await db.commit()

async def get_content_hash_messages(content_hash: str, limit: int = 10) -> List[Dict]:
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM messages WHERE content_hash = ? ORDER BY created_at DESC LIMIT ?", (content_hash, limit)) as cur:
            rows = await cur.fetchall()
            return [dict(row) for row in rows]

# -------------------- AI Evaluations --------------------
async def save_evaluation(message_id: int, channel_id: int, importance: float, urgency: float, confidence: float, event_type: str):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            "INSERT INTO evaluations (message_id, channel_id, importance, urgency, confidence, event_type) VALUES (?, ?, ?, ?, ?, ?)",
            (message_id, channel_id, importance, urgency, confidence, event_type)
        )
        await db.commit()

# -------------------- Event Clusters --------------------
async def add_cluster(cluster_hash: str, event_type: str, importance: float, urgency: float, confidence: float, channels: list, message_ids: list):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            "INSERT INTO clusters (cluster_hash, event_type, importance, urgency, confidence, first_seen, last_seen, message_count, channels) VALUES (?, ?, ?, ?, ?, datetime('now'), datetime('now'), ?, ?)",
            (cluster_hash, event_type, importance, urgency, confidence, len(message_ids), json.dumps(channels))
        )
        cluster_id = db.last_insert_rowid
        for msg_id, ch_id in message_ids:
            await db.execute("INSERT INTO cluster_messages (cluster_id, message_id, channel_id) VALUES (?, ?, ?)", (cluster_id, msg_id, ch_id))
        await db.commit()
        return cluster_id

async def update_cluster(cluster_id: int, importance: float, urgency: float, confidence: float, channels: list, message_ids: list):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            "UPDATE clusters SET last_seen = datetime('now'), message_count = message_count + ?, channels = ?, importance = ?, urgency = ?, confidence = ? WHERE id = ?",
            (len(message_ids), json.dumps(channels), importance, urgency, confidence, cluster_id)
        )
        for msg_id, ch_id in message_ids:
            await db.execute("INSERT INTO cluster_messages (cluster_id, message_id, channel_id) VALUES (?, ?, ?)", (cluster_id, msg_id, ch_id))
        await db.commit()

async def get_cluster_by_hash(cluster_hash: str) -> Optional[Dict]:
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM clusters WHERE cluster_hash = ?", (cluster_hash,)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None

async def get_recent_clusters(window_seconds: int) -> List[Dict]:
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM clusters WHERE last_seen > datetime('now', ?) ORDER BY last_seen DESC", (f'-{window_seconds} seconds',)) as cur:
            rows = await cur.fetchall()
            return [dict(row) for row in rows]

# -------------------- Team Management --------------------
async def add_user(user_id: int, username: str, role: str, desk: str = None):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO users (user_id, username, role, desk) VALUES (?, ?, ?, ?)",
            (user_id, username, role, desk)
        )
        await db.commit()

async def remove_user(user_id: int):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
        await db.commit()

async def get_users() -> List[Dict]:
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users") as cur:
            rows = await cur.fetchall()
            return [dict(row) for row in rows]

async def get_user(user_id: int) -> Optional[Dict]:
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None

async def update_user_role(user_id: int, role: str):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute("UPDATE users SET role = ? WHERE user_id = ?", (role, user_id))
        await db.commit()

# -------------------- Assignments --------------------
async def create_assignment(cluster_id: int, assigned_to: int, assigned_by: int, status: str = 'new'):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            "INSERT INTO assignments (cluster_id, assigned_to, assigned_by, status) VALUES (?, ?, ?, ?)",
            (cluster_id, assigned_to, assigned_by, status)
        )
        await db.commit()

async def update_assignment_status(cluster_id: int, status: str, assigned_by: int = None):
    async with aiosqlite.connect(config.DB_PATH) as db:
        if assigned_by:
            await db.execute(
                "UPDATE assignments SET status = ?, updated_at = datetime('now'), assigned_by = ? WHERE cluster_id = ?",
                (status, assigned_by, cluster_id)
            )
        else:
            await db.execute(
                "UPDATE assignments SET status = ?, updated_at = datetime('now') WHERE cluster_id = ?",
                (status, cluster_id)
            )
        await db.commit()

async def get_assignment(cluster_id: int) -> Optional[Dict]:
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM assignments WHERE cluster_id = ?", (cluster_id,)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None

# -------------------- Comments --------------------
async def add_comment(cluster_id: int, user_id: int, comment: str):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            "INSERT INTO comments (cluster_id, user_id, comment) VALUES (?, ?, ?)",
            (cluster_id, user_id, comment)
        )
        await db.commit()

async def get_comments(cluster_id: int) -> List[Dict]:
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM comments WHERE cluster_id = ? ORDER BY created_at", (cluster_id,)) as cur:
            rows = await cur.fetchall()
            return [dict(row) for row in rows]

# -------------------- Health Metrics --------------------
async def record_health(metric_name: str, value: float):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            "INSERT INTO health_metrics (metric_name, metric_value) VALUES (?, ?)",
            (metric_name, value)
        )
        await db.commit()

async def get_latest_metrics(limit: int = 100) -> List[Dict]:
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM health_metrics ORDER BY timestamp DESC LIMIT ?", (limit,)) as cur:
            rows = await cur.fetchall()
            return [dict(row) for row in rows]

# -------------------- Bot State --------------------
async def get_state(key: str, default: str = None) -> str:
    async with aiosqlite.connect(config.DB_PATH) as db:
        async with db.execute("SELECT value FROM bot_state WHERE key = ?", (key,)) as cur:
            row = await cur.fetchone()
            return row[0] if row else default

async def set_state(key: str, value: str):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute("REPLACE INTO bot_state (key, value) VALUES (?, ?)", (key, value))
        await db.commit()

async def increment_counter(key: str):
    val = int(await get_state(key, "0"))
    await set_state(key, str(val + 1))

async def update_last_activity():
    await set_state("last_activity", datetime.datetime.now(datetime.UTC).isoformat())

async def log_error(error: str):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute("INSERT INTO health_metrics (metric_name, metric_value) VALUES (?, ?)", ("error", 1))  # simple error count
        await db.commit()
    await set_state("last_error", error[:200])
