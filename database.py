from __future__ import annotations

import aiosqlite
from pathlib import Path
from typing import Any, Iterable

from config import settings


class Database:
    def __init__(self, path: str):
        self.path = path
        self.conn: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = await aiosqlite.connect(self.path)
        self.conn.row_factory = aiosqlite.Row
        await self.conn.execute("PRAGMA journal_mode=WAL;")
        await self.conn.execute("PRAGMA foreign_keys=ON;")
        await self.conn.execute("PRAGMA synchronous=NORMAL;")
        await self.init_schema()
        await self.apply_migrations()

    async def close(self) -> None:
        if self.conn:
            await self.conn.close()

    async def init_schema(self) -> None:
        assert self.conn is not None
        schema = """
        CREATE TABLE IF NOT EXISTS source_channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id INTEGER UNIQUE NOT NULL,
            title TEXT,
            username TEXT,
            enabled INTEGER DEFAULT 1,
            label TEXT,
            category TEXT,
            trust_score REAL DEFAULT 0.5,
            speed_score REAL DEFAULT 0.5,
            priority_score REAL DEFAULT 0.5,
            media_mode TEXT DEFAULT 'all',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS output_targets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            target_chat_id INTEGER UNIQUE NOT NULL,
            name TEXT NOT NULL,
            username TEXT,
            category TEXT,
            enabled INTEGER DEFAULT 1,
            media_mode TEXT DEFAULT 'all',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS routing_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_channel_id INTEGER,
            output_target_id INTEGER NOT NULL,
            min_importance REAL DEFAULT 0,
            min_urgency REAL DEFAULT 0,
            event_type TEXT,
            only_foreign INTEGER DEFAULT 0,
            media_mode TEXT DEFAULT 'all',
            enabled INTEGER DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(source_channel_id, output_target_id, event_type, media_mode),
            FOREIGN KEY(source_channel_id) REFERENCES source_channels(id) ON DELETE CASCADE,
            FOREIGN KEY(output_target_id) REFERENCES output_targets(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS forwarded_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id INTEGER NOT NULL,
            message_id INTEGER NOT NULL,
            grouped_id INTEGER,
            content_hash TEXT,
            normalized_hash TEXT,
            cluster_id INTEGER,
            forwarded_to INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(channel_id, message_id, forwarded_to)
        );

        CREATE TABLE IF NOT EXISTS ai_evaluations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id INTEGER NOT NULL,
            message_id INTEGER NOT NULL,
            importance_score REAL,
            urgency_score REAL,
            confidence_score REAL,
            event_type TEXT,
            summary TEXT,
            language TEXT,
            translated_text TEXT,
            mode TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(channel_id, message_id, mode)
        );

        CREATE TABLE IF NOT EXISTS event_clusters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cluster_key TEXT UNIQUE,
            event_type TEXT,
            summary TEXT,
            first_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
            last_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
            source_count INTEGER DEFAULT 1,
            confidence REAL DEFAULT 0.5
        );

        CREATE TABLE IF NOT EXISTS cluster_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cluster_id INTEGER NOT NULL,
            channel_id INTEGER NOT NULL,
            message_id INTEGER NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(cluster_id, channel_id, message_id),
            FOREIGN KEY(cluster_id) REFERENCES event_clusters(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_user_id INTEGER UNIQUE NOT NULL,
            username TEXT,
            full_name TEXT,
            role_name TEXT DEFAULT 'Monitor',
            is_active INTEGER DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id INTEGER,
            message_id INTEGER,
            assigned_to INTEGER,
            status TEXT DEFAULT 'new',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS internal_comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id INTEGER,
            message_id INTEGER,
            user_id INTEGER,
            comment TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS bot_state (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS error_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            component TEXT,
            error_text TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS health_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            component TEXT,
            metric_key TEXT,
            metric_value TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        """
        await self.conn.executescript(schema)
        await self.conn.commit()

    async def apply_migrations(self) -> None:
        await self._ensure_column("source_channels", "media_mode", "TEXT DEFAULT 'all'")
        await self._ensure_column("output_targets", "username", "TEXT")
        await self._ensure_column("output_targets", "media_mode", "TEXT DEFAULT 'all'")
        await self._ensure_column("output_targets", "updated_at", "DATETIME")
        await self._ensure_column("routing_rules", "media_mode", "TEXT DEFAULT 'all'")
        await self._ensure_column("routing_rules", "created_at", "DATETIME DEFAULT CURRENT_TIMESTAMP")
        await self._ensure_column("users", "role_name", "TEXT DEFAULT 'Monitor'")

    async def _ensure_column(self, table: str, column: str, decl: str) -> None:
        assert self.conn is not None
        async with self.conn.execute(f"PRAGMA table_info({table})") as cur:
            cols = [row[1] for row in await cur.fetchall()]
        if column not in cols:
            await self.conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")
            await self.conn.commit()

    async def execute(self, query: str, params: Iterable[Any] = ()) -> None:
        assert self.conn is not None
        await self.conn.execute(query, tuple(params))
        await self.conn.commit()

    async def fetchone(self, query: str, params: Iterable[Any] = ()) -> aiosqlite.Row | None:
        assert self.conn is not None
        async with self.conn.execute(query, tuple(params)) as cur:
            return await cur.fetchone()

    async def fetchall(self, query: str, params: Iterable[Any] = ()) -> list[aiosqlite.Row]:
        assert self.conn is not None
        async with self.conn.execute(query, tuple(params)) as cur:
            return await cur.fetchall()

    async def upsert_source(self, channel_id: int, title: str, username: str | None) -> None:
        await self.execute(
            """
            INSERT INTO source_channels(channel_id, title, username)
            VALUES (?, ?, ?)
            ON CONFLICT(channel_id) DO UPDATE SET
                title=excluded.title,
                username=excluded.username,
                updated_at=CURRENT_TIMESTAMP
            """,
            (channel_id, title, username),
        )

    async def add_or_update_target(self, target_chat_id: int, name: str, username: str | None = None) -> None:
        await self.execute(
            """
            INSERT INTO output_targets(target_chat_id, name, username)
            VALUES (?, ?, ?)
            ON CONFLICT(target_chat_id) DO UPDATE SET
                name=excluded.name,
                username=excluded.username,
                updated_at=CURRENT_TIMESTAMP
            """,
            (target_chat_id, name, username),
        )

    async def get_enabled_sources(self) -> list[aiosqlite.Row]:
        return await self.fetchall("SELECT * FROM source_channels WHERE enabled = 1 ORDER BY priority_score DESC, id DESC")

    async def get_sources(self, limit: int = 100, offset: int = 0) -> list[aiosqlite.Row]:
        return await self.fetchall(
            "SELECT * FROM source_channels ORDER BY enabled DESC, priority_score DESC, id DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )

    async def get_source_by_id(self, source_id: int) -> aiosqlite.Row | None:
        return await self.fetchone("SELECT * FROM source_channels WHERE id = ?", (source_id,))

    async def set_source_enabled(self, source_id: int, enabled: bool) -> None:
        await self.execute("UPDATE source_channels SET enabled=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (1 if enabled else 0, source_id))

    async def set_all_sources_enabled(self, enabled: bool) -> None:
        await self.execute("UPDATE source_channels SET enabled=?, updated_at=CURRENT_TIMESTAMP", (1 if enabled else 0,))

    async def set_source_media_mode(self, source_id: int, media_mode: str) -> None:
        await self.execute("UPDATE source_channels SET media_mode=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (media_mode, source_id))

    async def get_output_targets(self) -> list[aiosqlite.Row]:
        return await self.fetchall("SELECT * FROM output_targets WHERE enabled = 1 ORDER BY id DESC")

    async def get_all_targets(self) -> list[aiosqlite.Row]:
        return await self.fetchall("SELECT * FROM output_targets ORDER BY enabled DESC, id DESC")

    async def get_target_by_id(self, target_id: int) -> aiosqlite.Row | None:
        return await self.fetchone("SELECT * FROM output_targets WHERE id = ?", (target_id,))

    async def set_target_enabled(self, target_id: int, enabled: bool) -> None:
        await self.execute("UPDATE output_targets SET enabled=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (1 if enabled else 0, target_id))

    async def set_target_media_mode(self, target_id: int, media_mode: str) -> None:
        await self.execute("UPDATE output_targets SET media_mode=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (media_mode, target_id))

    async def create_or_update_route(
        self,
        source_channel_id: int | None,
        output_target_id: int,
        min_importance: float = 0.0,
        min_urgency: float = 0.0,
        event_type: str | None = None,
        only_foreign: bool = False,
        media_mode: str = "all",
    ) -> None:
        existing = await self.fetchone(
            """
            SELECT id FROM routing_rules
            WHERE ((source_channel_id = ?) OR (source_channel_id IS NULL AND ? IS NULL))
              AND output_target_id = ?
              AND IFNULL(event_type, '') = IFNULL(?, '')
              AND IFNULL(media_mode, 'all') = IFNULL(?, 'all')
            """,
            (source_channel_id, source_channel_id, output_target_id, event_type, media_mode),
        )
        if existing:
            await self.execute(
                "UPDATE routing_rules SET min_importance=?, min_urgency=?, only_foreign=?, enabled=1 WHERE id=?",
                (min_importance, min_urgency, 1 if only_foreign else 0, existing["id"]),
            )
        else:
            await self.execute(
                """
                INSERT INTO routing_rules(source_channel_id, output_target_id, min_importance, min_urgency, event_type, only_foreign, media_mode, enabled)
                VALUES (?, ?, ?, ?, ?, ?, ?, 1)
                """,
                (source_channel_id, output_target_id, min_importance, min_urgency, event_type, 1 if only_foreign else 0, media_mode),
            )

    async def get_routes(self, limit: int = 200) -> list[aiosqlite.Row]:
        return await self.fetchall(
            """
            SELECT rr.*, sc.title as source_title, ot.name as target_name, ot.target_chat_id
            FROM routing_rules rr
            JOIN output_targets ot ON ot.id = rr.output_target_id
            LEFT JOIN source_channels sc ON sc.id = rr.source_channel_id
            ORDER BY rr.id DESC
            LIMIT ?
            """,
            (limit,),
        )

    async def insert_health(self, component: str, metric_key: str, metric_value: str) -> None:
        await self.execute(
            "INSERT INTO health_logs(component, metric_key, metric_value) VALUES (?, ?, ?)",
            (component, metric_key, metric_value),
        )

    async def log_error(self, component: str, error_text: str) -> None:
        await self.execute(
            "INSERT INTO error_logs(component, error_text) VALUES (?, ?)",
            (component, error_text[:4000]),
        )


db = Database(settings.sqlite_path)
