"""SQLite database management for mcp-feed-reader-crunchtools."""

from __future__ import annotations

import sqlite3
from typing import Any

from .config import get_config

_db: sqlite3.Connection | None = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS feeds (
    id INTEGER PRIMARY KEY,
    url TEXT UNIQUE NOT NULL,
    title TEXT,
    site_url TEXT,
    category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL,
    last_fetched TEXT,
    etag TEXT,
    last_modified TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS entries (
    id INTEGER PRIMARY KEY,
    feed_id INTEGER NOT NULL REFERENCES feeds(id) ON DELETE CASCADE,
    guid TEXT NOT NULL,
    title TEXT,
    url TEXT,
    author TEXT,
    content TEXT,
    published TEXT,
    is_read INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(feed_id, guid)
);

CREATE VIRTUAL TABLE IF NOT EXISTS entries_fts USING fts5(
    title, content, content=entries, content_rowid=id
);

CREATE TRIGGER IF NOT EXISTS entries_ai AFTER INSERT ON entries BEGIN
    INSERT INTO entries_fts(rowid, title, content)
    VALUES (new.id, new.title, new.content);
END;

CREATE TRIGGER IF NOT EXISTS entries_ad AFTER DELETE ON entries BEGIN
    INSERT INTO entries_fts(entries_fts, rowid, title, content)
    VALUES ('delete', old.id, old.title, old.content);
END;

CREATE TRIGGER IF NOT EXISTS entries_au AFTER UPDATE ON entries BEGIN
    INSERT INTO entries_fts(entries_fts, rowid, title, content)
    VALUES ('delete', old.id, old.title, old.content);
    INSERT INTO entries_fts(rowid, title, content)
    VALUES (new.id, new.title, new.content);
END;
"""


def get_db(db_path: str | None = None) -> sqlite3.Connection:
    """Get or create the singleton database connection."""
    global _db
    if _db is None:
        path = db_path or get_config().db_path
        get_config().ensure_db_dir()
        _db = sqlite3.connect(path)
        _db.row_factory = sqlite3.Row
        _db.execute("PRAGMA journal_mode=WAL")
        _db.execute("PRAGMA foreign_keys=ON")
        _db.executescript(SCHEMA)
    return _db


def query(sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    """Execute a SELECT query and return results as dicts."""
    db = get_db()
    cursor = db.execute(sql, params)
    return [dict(row) for row in cursor.fetchall()]


def query_one(sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
    """Execute a SELECT query and return a single result or None."""
    db = get_db()
    cursor = db.execute(sql, params)
    row = cursor.fetchone()
    return dict(row) if row else None


def execute(sql: str, params: tuple[Any, ...] = ()) -> int:
    """Execute an INSERT/UPDATE/DELETE and return lastrowid."""
    db = get_db()
    cursor = db.execute(sql, params)
    db.commit()
    return cursor.lastrowid or 0


def execute_many(sql: str, params_list: list[tuple[Any, ...]]) -> None:
    """Execute a statement with multiple parameter sets."""
    db = get_db()
    db.executemany(sql, params_list)
    db.commit()
