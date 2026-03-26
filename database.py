import sqlite3
import aiosqlite
import json
import datetime
from typing import List, Dict, Any, Optional, Tuple
import config

# ---------- Synchronous initialization ----------
def init_sync_db():
    conn = sqlite3.connect(config.DB_PATH)
    c = conn.cursor()

    # ---- Source Channels (with scoring) ----
    c.execute('''
        CREATE TABLE IF NOT EXISTS source_channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id INTEGER NOT NULL UNIQUE,
            username TEXT,
            title TEXT,
            label TEXT,
            category TEXT,
            enabled INTEGER DEFAULT 1,
            priority TEXT DEFAULT 'normal',
            filters_enabled INTEGER DEFAULT 1,
            trust_score REAL DEFAULT 0.5,
            speed_score REAL DEFAULT 0.5,
            priority_score REAL DEFAULT 0.5,
            language TEXT,
            region TEXT
        )
    ''')

    # ---- Forwarded Messages (with dedup) ----
    c.execute('''
        CREATE TABLE IF NOT EXISTS forwarded_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_channel_id INTEGER NOT NULL,
            message_id INTEGER NOT NULL,
            content_hash TEXT,
            grouped_id INTEGER,
            normalized_text TEXT,
            forwarded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(source_channel_id, message_id)
        )
    ''')

    # ---- Keyword Filters (global) ----
    c.execute('''
        CREATE TABLE IF NOT EXISTS keyword_filters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL,
            keyword TEXT NOT NULL,
            is_regex INTEGER DEFAULT 0,
            case_sensitive INTEGER DEFAULT 0,
            UNIQUE(type, keyword)
        )
    ''')

    # ---- Channel-specific Filters ----
    c.execute('''
        CREATE TABLE IF NOT EXISTS channel_filters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id INTEGER NOT NULL,
            filter_type TEXT NOT NULL,
            keyword TEXT NOT NULL,
            is_regex INTEGER DEFAULT 0,
            case_sensitive INTEGER DEFAULT 0,
            FOREIGN KEY(channel_id) REFERENCES source_channels(channel_id)
        )
    ''')

    # ---- Content Type Filters (global) ----
    c.execute('''
        CREATE TABLE IF NOT EXISTS content_type_filters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content_type TEXT NOT NULL UNIQUE
        )
    ''')
    # Insert defaults if empty
    for t in config.DEFAULT_CONTENT_TYPES:
        c.execute("INSERT OR IGNORE INTO content_type_filters (content_type) VALUES (?)", (t,))

    # ---- Language Filters (global) ----
    c.execute('''
        CREATE TABLE IF NOT EXISTS language_filters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            language_code TEXT NOT NULL UNIQUE
        )
    ''')

    # ---- Forward Targets ----
    c.execute('''
        CREATE TABLE IF NOT EXISTS forward_targets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            target_type TEXT NOT NULL,   -- primary, backup, alert, normal_feed, priority_feed, critical_alert
            target_identifier TEXT NOT NULL,
            enabled INTEGER DEFAULT 1,
            UNIQUE(target_type)
        )
    ''')

    # ---- Bot State ----
    c.execute('''
        CREATE TABLE IF NOT EXISTS bot_state (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    default_state = {
        'is_running': '0',
        'forward_mode': config.DEFAULT_FORWARD_MODE,
        'last_error': '',
        'last_activity': '',
        'total_forwarded': '0',
        'total_alerts': '0',
        'start_time': '',
        'uptime': '0',
        'ai_enabled': str(int(config.AI_ENABLED)),
        'ai_fast_mode': str(int(config.AI_FAST_MODE)),
        'ai_importance_threshold': str(config.AI_IMPORTANCE_THRESHOLD),
        'ai_urgency_threshold': str(config.AI_URGENCY_THRESHOLD),
        'ai_confidence_threshold': str(config.AI_CONFIDENCE_THRESHOLD),
        'deep_analysis_enabled': str(int(config.DEEP_ANALYSIS_ENABLED)),
        'correlation_window': str(config.AI_CORRELATION_WINDOW)
    }
    for key, val in default_state.items():
        c.execute("INSERT OR IGNORE INTO bot_state (key, value) VALUES (?, ?)", (key, val))

    # ---- Error Logs ----
    c.execute('''
        CREATE TABLE IF NOT EXISTS error_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            error TEXT
        )
    ''')

    # ---- Daily Stats ----
    c.execute('''
        CREATE TABLE IF NOT EXISTS daily_stats (
            date TEXT PRIMARY KEY,
            total_messages INTEGER DEFAULT 0,
            total_alerts INTEGER DEFAULT 0,
            channels_activity TEXT   -- JSON: {channel_id: count}
        )
    ''')

    # ---- AI Evaluations ----
    c.execute('''
        CREATE TABLE IF NOT EXISTS ai_evaluations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id INTEGER NOT NULL,
            channel_id INTEGER NOT NULL,
            importance_score REAL,
            urgency_score REAL,
            confidence REAL,
            event_type TEXT,
            evaluated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(message_id, channel_id) REFERENCES forwarded_messages(message_id, source_channel_id)
        )
    ''')

    # ---- Event Clusters (Correlation) ----
    c.execute('''
        CREATE TABLE IF NOT EXISTS event_clusters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cluster_hash TEXT UNIQUE,
            event_type TEXT,
            importance REAL,
            urgency REAL,
            confidence REAL,
            first_seen TIMESTAMP,
            last_seen TIMESTAMP,
            message_count INTEGER,
            channels TEXT,        -- JSON list of channel ids
            status TEXT DEFAULT 'new'   -- new, under_review, confirmed, published, rejected
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS cluster_messages (
            cluster_id INTEGER,
            message_id INTEGER,
            channel_id INTEGER,
            FOREIGN KEY(cluster_id) REFERENCES event_clusters(id),
            FOREIGN KEY(message_id, channel_id) REFERENCES forwarded_messages(message_id, source_channel_id)
        )
    ''')

    # ---- Team Members ----
    c.execute('''
        CREATE TABLE IF NOT EXISTS team_members (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            role TEXT NOT NULL,   -- admin, analyst, editor, monitor
            desk TEXT,            -- category assigned
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # ---- Assignments ----
    c.execute('''
        CREATE TABLE IF NOT EXISTS assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cluster_id INTEGER,
            assigned_to INTEGER,
            assigned_by INTEGER,
            status TEXT DEFAULT 'new',   -- new, under_review, confirmed, published, rejected
            comment TEXT,
            assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(cluster_id) REFERENCES event_clusters(id),
            FOREIGN KEY(assigned_to) REFERENCES team_members(user_id),
            FOREIGN KEY(assigned_by) REFERENCES team_members(user_id)
        )
    ''')
    # ---- Comments ----
    c.execute('''
        CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cluster_id INTEGER,
            user_id INTEGER,
            comment TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(cluster_id) REFERENCES event_clusters(id),
            FOREIGN KEY(user_id) REFERENCES team_members(user_id)
        )
    ''')

    # ---- Health Metrics ----
    c.execute('''
        CREATE TABLE IF NOT EXISTS health_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            metric_name TEXT,
            metric_value REAL
        )
    ''')

    conn.commit()
    conn.close()

# ---------- Async helpers ----------
async def get_db():
    return await aiosqlite.connect(config.DB_PATH)

# ---------- Source Channels ----------
async def add_source_channel(channel_id: int, username: str = None, title: str = None, label: str = None, category: str = None,
                             trust_score: float = config.DEFAULT_TRUST_SCORE,
                             speed_score: float = config.DEFAULT_SPEED_SCORE,
                             priority_score: float = config.DEFAULT_PRIORITY_SCORE,
                             language: str = None, region: str = None) -> bool:
    async with await get_db() as db:
        try:
            await db.execute(
                """INSERT INTO source_channels 
                   (channel_id, username, title, label, category, trust_score, speed_score, priority_score, language, region)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (channel_id, username, title, label, category, trust_score, speed_score, priority_score, language, region)
            )
            await db.commit()
            return True
        except sqlite3.IntegrityError:
            return False

async def remove_source_channel(channel_id: int):
    async with await get_db() as db:
        await db.execute("DELETE FROM source_channels WHERE channel_id = ?", (channel_id,))
        await db.commit()

async def get_all_channels() -> List[Dict]:
    async with await get_db() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM source_channels") as cur:
            rows = await cur.fetchall()
            return [dict(row) for row in rows]

async def get_channel(channel_id: int) -> Optional[Dict]:
    async with await get_db() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM source_channels WHERE channel_id = ?", (channel_id,)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None

async def update_channel_field(channel_id: int, field: str, value):
    async with await get_db() as db:
        await db.execute(f"UPDATE source_channels SET {field} = ? WHERE channel_id = ?", (value, channel_id))
        await db.commit()

async def toggle_channel_enabled(channel_id: int, enabled: bool):
    await update_channel_field(channel_id, "enabled", 1 if enabled else 0)

async def update_channel_label(channel_id: int, label: str):
    await update_channel_field(channel_id, "label", label)

async def update_channel_category(channel_id: int, category: str):
    await update_channel_field(channel_id, "category", category)

async def update_channel_priority(channel_id: int, priority: str):
    await update_channel_field(channel_id, "priority", priority)

async def update_channel_filters_enabled(channel_id: int, enabled: bool):
    await update_channel_field(channel_id, "filters_enabled", 1 if enabled else 0)

async def update_channel_scores(channel_id: int, trust_score: float = None, speed_score: float = None, priority_score: float = None):
    updates = []
    values = []
    if trust_score is not None:
        updates.append("trust_score = ?")
        values.append(trust_score)
    if speed_score is not None:
        updates.append("speed_score = ?")
        values.append(speed_score)
    if priority_score is not None:
        updates.append("priority_score = ?")
        values.append(priority_score)
    if updates:
        values.append(channel_id)
        async with await get_db() as db:
            await db.execute(f"UPDATE source_channels SET {', '.join(updates)} WHERE channel_id = ?", values)
            await db.commit()

# ---------- Forwarded Messages ----------
async def is_message_forwarded(channel_id: int, message_id: int) -> bool:
    async with await get_db() as db:
        async with db.execute("SELECT 1 FROM forwarded_messages WHERE source_channel_id = ? AND message_id = ?", (channel_id, message_id)) as cur:
            return await cur.fetchone() is not None

async def mark_message_forwarded(channel_id: int, message_id: int, content_hash: str = None, grouped_id: int = None, normalized_text: str = None):
    async with await get_db() as db:
        await db.execute(
            "INSERT INTO forwarded_messages (source_channel_id, message_id, content_hash, grouped_id, normalized_text) VALUES (?, ?, ?, ?, ?)",
            (channel_id, message_id, content_hash, grouped_id, normalized_text)
        )
        await db.commit()

async def is_content_duplicate(content_hash: str) -> bool:
    async with await get_db() as db:
        async with db.execute("SELECT 1 FROM forwarded_messages WHERE content_hash = ?", (content_hash,)) as cur:
            return await cur.fetchone() is not None

# ---------- Keyword Filters (Global) ----------
async def add_keyword_filter(filter_type: str, keyword: str, is_regex: bool = False, case_sensitive: bool = False) -> bool:
    async with await get_db() as db:
        try:
            await db.execute(
                "INSERT INTO keyword_filters (type, keyword, is_regex, case_sensitive) VALUES (?, ?, ?, ?)",
                (filter_type, keyword, 1 if is_regex else 0, 1 if case_sensitive else 0)
            )
            await db.commit()
            return True
        except sqlite3.IntegrityError:
            return False

async def remove_keyword_filter(filter_type: str, keyword: str):
    async with await get_db() as db:
        await db.execute("DELETE FROM keyword_filters WHERE type = ? AND keyword = ?", (filter_type, keyword))
        await db.commit()

async def get_keyword_filters() -> Dict[str, List[Tuple[str, bool, bool]]]:
    async with await get_db() as db:
        include = []
        exclude = []
        async with db.execute("SELECT keyword, is_regex, case_sensitive FROM keyword_filters WHERE type = 'include'") as cur:
            include = await cur.fetchall()
        async with db.execute("SELECT keyword, is_regex, case_sensitive FROM keyword_filters WHERE type = 'exclude'") as cur:
            exclude = await cur.fetchall()
        return {'include': include, 'exclude': exclude}

# ---------- Channel Filters ----------
async def add_channel_filter(channel_id: int, filter_type: str, keyword: str, is_regex: bool = False, case_sensitive: bool = False):
    async with await get_db() as db:
        await db.execute(
            "INSERT INTO channel_filters (channel_id, filter_type, keyword, is_regex, case_sensitive) VALUES (?, ?, ?, ?, ?)",
            (channel_id, filter_type, keyword, 1 if is_regex else 0, 1 if case_sensitive else 0)
        )
        await db.commit()

async def remove_channel_filter(channel_id: int, filter_type: str, keyword: str):
    async with await get_db() as db:
        await db.execute("DELETE FROM channel_filters WHERE channel_id = ? AND filter_type = ? AND keyword = ?", (channel_id, filter_type, keyword))
        await db.commit()

async def get_channel_filters(channel_id: int) -> Dict[str, List[Tuple[str, bool, bool]]]:
    async with await get_db() as db:
        include = []
        exclude = []
        async with db.execute("SELECT keyword, is_regex, case_sensitive FROM channel_filters WHERE channel_id = ? AND filter_type = 'include'", (channel_id,)) as cur:
            include = await cur.fetchall()
        async with db.execute("SELECT keyword, is_regex, case_sensitive FROM channel_filters WHERE channel_id = ? AND filter_type = 'exclude'", (channel_id,)) as cur:
            exclude = await cur.fetchall()
        return {'include': include, 'exclude': exclude}

# ---------- Content Type Filters ----------
async def set_content_type_filters(types: List[str]):
    async with await get_db() as db:
        await db.execute("DELETE FROM content_type_filters")
        for t in types:
            await db.execute("INSERT INTO content_type_filters (content_type) VALUES (?)", (t,))
        await db.commit()

async def get_content_type_filters() -> List[str]:
    async with await get_db() as db:
        async with db.execute("SELECT content_type FROM content_type_filters") as cur:
            rows = await cur.fetchall()
            return [row[0] for row in rows] if rows else config.DEFAULT_CONTENT_TYPES.copy()

# ---------- Language Filters ----------
async def add_language_filter(lang_code: str):
    async with await get_db() as db:
        await db.execute("INSERT OR IGNORE INTO language_filters (language_code) VALUES (?)", (lang_code,))
        await db.commit()

async def remove_language_filter(lang_code: str):
    async with await get_db() as db:
        await db.execute("DELETE FROM language_filters WHERE language_code = ?", (lang_code,))
        await db.commit()

async def get_language_filters() -> List[str]:
    async with await get_db() as db:
        async with db.execute("SELECT language_code FROM language_filters") as cur:
            rows = await cur.fetchall()
            return [row[0] for row in rows]

# ---------- Forward Targets ----------
async def set_forward_target(target_type: str, identifier: str):
    async with await get_db() as db:
        await db.execute("REPLACE INTO forward_targets (target_type, target_identifier) VALUES (?, ?)", (target_type, identifier))
        await db.commit()

async def get_forward_target(target_type: str) -> Optional[str]:
    async with await get_db() as db:
        async with db.execute("SELECT target_identifier FROM forward_targets WHERE target_type = ? AND enabled = 1", (target_type,)) as cur:
            row = await cur.fetchone()
            return row[0] if row else None

async def get_all_forward_targets() -> Dict[str, str]:
    primary = await get_forward_target('primary')
    backup = await get_forward_target('backup')
    alert = await get_forward_target('alert')
    normal_feed = await get_forward_target('normal_feed')
    priority_feed = await get_forward_target('priority_feed')
    critical_alert = await get_forward_target('critical_alert')
    return {
        'primary': primary, 'backup': backup, 'alert': alert,
        'normal_feed': normal_feed, 'priority_feed': priority_feed, 'critical_alert': critical_alert
    }

# ---------- Bot State ----------
async def get_bot_state(key: str, default=None):
    async with await get_db() as db:
        async with db.execute("SELECT value FROM bot_state WHERE key = ?", (key,)) as cur:
            row = await cur.fetchone()
            return row[0] if row else default

async def set_bot_state(key: str, value: str):
    async with await get_db() as db:
        await db.execute("REPLACE INTO bot_state (key, value) VALUES (?, ?)", (key, value))
        await db.commit()

async def increment_total_forwarded():
    current = int(await get_bot_state("total_forwarded", "0"))
    await set_bot_state("total_forwarded", str(current + 1))

async def increment_total_alerts():
    current = int(await get_bot_state("total_alerts", "0"))
    await set_bot_state("total_alerts", str(current + 1))

async def update_last_activity():
    await set_bot_state("last_activity", datetime.datetime.utcnow().isoformat())

async def log_error(error: str):
    async with await get_db() as db:
        await db.execute("INSERT INTO error_logs (error) VALUES (?)", (error,))
        await db.commit()
    await set_bot_state("last_error", error[:200])

# ---------- AI Evaluations ----------
async def save_ai_evaluation(message_id: int, channel_id: int, scores: dict):
    async with await get_db() as db:
        await db.execute(
            "INSERT INTO ai_evaluations (message_id, channel_id, importance_score, urgency_score, confidence, event_type) VALUES (?, ?, ?, ?, ?, ?)",
            (message_id, channel_id, scores.get('importance', 0), scores.get('urgency', 0), scores.get('confidence', 0), scores.get('event_type', 'unknown'))
        )
        await db.commit()

# ---------- Event Clusters ----------
async def add_event_cluster(cluster_hash: str, event_type: str, importance: float, urgency: float, confidence: float, channels: list, message_ids: list):
    async with await get_db() as db:
        await db.execute(
            "INSERT INTO event_clusters (cluster_hash, event_type, importance, urgency, confidence, first_seen, last_seen, message_count, channels) VALUES (?, ?, ?, ?, ?, datetime('now'), datetime('now'), ?, ?)",
            (cluster_hash, event_type, importance, urgency, confidence, len(message_ids), json.dumps(channels))
        )
        cluster_id = db.last_insert_rowid
        for msg_id, ch_id in message_ids:
            await db.execute("INSERT INTO cluster_messages (cluster_id, message_id, channel_id) VALUES (?, ?, ?)", (cluster_id, msg_id, ch_id))
        await db.commit()
        return cluster_id

async def update_event_cluster(cluster_id: int, importance: float, urgency: float, confidence: float, channels: list, message_ids: list):
    async with await get_db() as db:
        await db.execute(
            "UPDATE event_clusters SET last_seen = datetime('now'), message_count = message_count + ?, channels = ?, importance = ?, urgency = ?, confidence = ? WHERE id = ?",
            (len(message_ids), json.dumps(channels), importance, urgency, confidence, cluster_id)
        )
        for msg_id, ch_id in message_ids:
            await db.execute("INSERT INTO cluster_messages (cluster_id, message_id, channel_id) VALUES (?, ?, ?)", (cluster_id, msg_id, ch_id))
        await db.commit()

async def get_existing_cluster(content_hash: str, window_seconds: int) -> Optional[int]:
    async with await get_db() as db:
        async with db.execute('''
            SELECT c.id FROM event_clusters c
            JOIN cluster_messages cm ON c.id = cm.cluster_id
            JOIN forwarded_messages fm ON cm.message_id = fm.message_id AND cm.channel_id = fm.source_channel_id
            WHERE fm.content_hash = ? AND c.last_seen > datetime('now', ?)
            LIMIT 1
        ''', (content_hash, f'-{window_seconds} seconds')) as cur:
            row = await cur.fetchone()
            return row[0] if row else None

async def get_event_cluster_by_id(cluster_id: int) -> Optional[Dict]:
    async with await get_db() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM event_clusters WHERE id = ?", (cluster_id,)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None

async def update_event_cluster_status(cluster_id: int, status: str):
    async with await get_db() as db:
        await db.execute("UPDATE event_clusters SET status = ? WHERE id = ?", (status, cluster_id))
        await db.commit()

# ---------- Team Management ----------
async def add_team_member(user_id: int, username: str, role: str, desk: str = None):
    async with await get_db() as db:
        await db.execute(
            "INSERT OR REPLACE INTO team_members (user_id, username, role, desk) VALUES (?, ?, ?, ?)",
            (user_id, username, role, desk)
        )
        await db.commit()

async def remove_team_member(user_id: int):
    async with await get_db() as db:
        await db.execute("DELETE FROM team_members WHERE user_id = ?", (user_id,))
        await db.commit()

async def get_team_members() -> List[Dict]:
    async with await get_db() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM team_members") as cur:
            rows = await cur.fetchall()
            return [dict(row) for row in rows]

async def get_team_member(user_id: int) -> Optional[Dict]:
    async with await get_db() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM team_members WHERE user_id = ?", (user_id,)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None

async def update_member_role(user_id: int, role: str):
    async with await get_db() as db:
        await db.execute("UPDATE team_members SET role = ? WHERE user_id = ?", (role, user_id))
        await db.commit()

# ---------- Assignments ----------
async def create_assignment(cluster_id: int, assigned_to: int, assigned_by: int, status: str = 'new'):
    async with await get_db() as db:
        await db.execute(
            "INSERT INTO assignments (cluster_id, assigned_to, assigned_by, status) VALUES (?, ?, ?, ?)",
            (cluster_id, assigned_to, assigned_by, status)
        )
        await db.commit()

async def update_assignment_status(cluster_id: int, status: str, assigned_by: int = None):
    async with await get_db() as db:
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

async def get_assignment_by_cluster(cluster_id: int) -> Optional[Dict]:
    async with await get_db() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM assignments WHERE cluster_id = ?", (cluster_id,)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None

# ---------- Comments ----------
async def add_comment(cluster_id: int, user_id: int, comment: str):
    async with await get_db() as db:
        await db.execute(
            "INSERT INTO comments (cluster_id, user_id, comment) VALUES (?, ?, ?)",
            (cluster_id, user_id, comment)
        )
        await db.commit()

async def get_comments(cluster_id: int) -> List[Dict]:
    async with await get_db() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM comments WHERE cluster_id = ? ORDER BY created_at", (cluster_id,)) as cur:
            rows = await cur.fetchall()
            return [dict(row) for row in rows]

# ---------- Daily Stats ----------
async def update_daily_stats(channel_id: int, is_alert: bool = False):
    today = datetime.date.today().isoformat()
    async with await get_db() as db:
        async with db.execute("SELECT channels_activity FROM daily_stats WHERE date = ?", (today,)) as cur:
            row = await cur.fetchone()
            if row:
                activity = json.loads(row[0])
                activity[str(channel_id)] = activity.get(str(channel_id), 0) + 1
                await db.execute(
                    "UPDATE daily_stats SET total_messages = total_messages + 1, total_alerts = total_alerts + ?, channels_activity = ? WHERE date = ?",
                    (1 if is_alert else 0, json.dumps(activity), today)
                )
            else:
                activity = {str(channel_id): 1}
                await db.execute(
                    "INSERT INTO daily_stats (date, total_messages, total_alerts, channels_activity) VALUES (?, ?, ?, ?)",
                    (today, 1, 1 if is_alert else 0, json.dumps(activity))
                )
        await db.commit()

async def get_daily_stats(days=7) -> Dict:
    result = {}
    async with await get_db() as db:
        for i in range(days):
            date = (datetime.date.today() - datetime.timedelta(days=i)).isoformat()
            async with db.execute("SELECT total_messages, total_alerts, channels_activity FROM daily_stats WHERE date = ?", (date,)) as cur:
                row = await cur.fetchone()
                if row:
                    result[date] = {
                        'total_messages': row[0],
                        'total_alerts': row[1],
                        'channels': json.loads(row[2]) if row[2] else {}
                    }
                else:
                    result[date] = {'total_messages': 0, 'total_alerts': 0, 'channels': {}}
    return result

# ---------- Health Metrics ----------
async def record_health_metric(metric_name: str, metric_value: float):
    async with await get_db() as db:
        await db.execute(
            "INSERT INTO health_metrics (metric_name, metric_value) VALUES (?, ?)",
            (metric_name, metric_value)
        )
        await db.commit()

async def get_latest_health_metrics(limit: int = 100) -> List[Dict]:
    async with await get_db() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM health_metrics ORDER BY timestamp DESC LIMIT ?", (limit,)) as cur:
            rows = await cur.fetchall()
            return [dict(row) for row in rows]
