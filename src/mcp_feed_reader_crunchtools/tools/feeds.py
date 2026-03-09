"""Feed management tools."""

from __future__ import annotations

import contextlib
import sqlite3
from datetime import datetime, timezone
from typing import Any

from .. import database as db
from ..errors import DuplicateFeedError, FeedNotFoundError
from ..fetcher import fetch_feed
from ..models import FeedInput

_FEED_LIST_SQL = """
    SELECT f.*, c.name AS category_name,
        (SELECT COUNT(*) FROM entries e
         WHERE e.feed_id = f.id AND e.is_read = 0) AS unread_count,
        (SELECT COUNT(*) FROM entries e
         WHERE e.feed_id = f.id) AS total_entries
    FROM feeds f
    LEFT JOIN categories c ON f.category_id = c.id
"""

_INSERT_ENTRY_SQL = """
    INSERT INTO entries
    (feed_id, guid, title, url, author, content, published)
    VALUES (?, ?, ?, ?, ?, ?, ?)
"""

_UPDATE_FEED_SQL = """
    UPDATE feeds SET title = ?, site_url = ?, etag = ?,
    last_modified = ?, last_fetched = ? WHERE id = ?
"""


def _insert_entries(
    parent_id: int, entries: list[dict[str, Any]]
) -> int:
    """Insert entries, skipping duplicates. Returns count of new entries."""
    new_count = 0
    for entry in entries:
        with contextlib.suppress(sqlite3.IntegrityError):
            db.execute(
                _INSERT_ENTRY_SQL,
                (
                    parent_id, entry["guid"], entry["title"],
                    entry["url"], entry["author"], entry["content"],
                    entry["published"],
                ),
            )
            new_count += 1
    return new_count


async def add_feed(url: str, category: str | None = None) -> dict[str, Any]:
    """Add a feed by URL, optionally assign to a category."""
    validated = FeedInput(url=url, category=category)
    url, category = validated.url, validated.category
    category_id = None
    if category:
        row = db.query_one(
            "SELECT id FROM categories WHERE name = ?", (category,)
        )
        if row:
            category_id = row["id"]
        else:
            category_id = db.execute(
                "INSERT INTO categories (name) VALUES (?)", (category,)
            )

    try:
        feed_id = db.execute(
            "INSERT INTO feeds (url, category_id) VALUES (?, ?)",
            (url, category_id),
        )
    except sqlite3.IntegrityError as exc:
        raise DuplicateFeedError(url) from exc

    result = await fetch_feed(url)
    if result:
        now = datetime.now(timezone.utc).isoformat()
        db.execute(
            _UPDATE_FEED_SQL,
            (result.title, result.site_url, result.etag,
             result.last_modified, now, feed_id),
        )
        _insert_entries(feed_id, result.entries)

    row = db.query_one("SELECT * FROM feeds WHERE id = ?", (feed_id,))
    assert row is not None
    return row


async def list_feeds(category_id: int | None = None) -> list[dict[str, Any]]:
    """List all feeds with unread counts, optionally filtered by category."""
    if category_id is not None:
        return db.query(
            _FEED_LIST_SQL + " WHERE f.category_id = ? ORDER BY f.title",
            (category_id,),
        )
    return db.query(_FEED_LIST_SQL + " ORDER BY f.title")


async def get_feed(feed_id: int) -> dict[str, Any]:
    """Get details for a single feed."""
    row = db.query_one(
        _FEED_LIST_SQL + " WHERE f.id = ?", (feed_id,)
    )
    if not row:
        raise FeedNotFoundError(feed_id)
    return row


async def delete_feed(feed_id: int) -> str:
    """Remove a feed and all its entries."""
    existing = db.query_one(
        "SELECT title, url FROM feeds WHERE id = ?", (feed_id,)
    )
    if not existing:
        raise FeedNotFoundError(feed_id)
    db.execute("DELETE FROM feeds WHERE id = ?", (feed_id,))
    return f"Deleted feed: {existing['title'] or existing['url']}"


async def fetch_feeds(feed_id: int | None = None) -> str:
    """Fetch new entries for all feeds or a specific feed."""
    if feed_id is not None:
        existing = db.query_one(
            "SELECT * FROM feeds WHERE id = ?", (feed_id,)
        )
        if not existing:
            raise FeedNotFoundError(feed_id)
        feeds_to_fetch = [existing]
    else:
        feeds_to_fetch = db.query("SELECT * FROM feeds ORDER BY id")

    total_new = 0
    errors: list[str] = []

    for feed in feeds_to_fetch:
        try:
            result = await fetch_feed(
                feed["url"],
                etag=feed.get("etag"),
                last_modified=feed.get("last_modified"),
            )
        except Exception as exc:
            errors.append(f"{feed['title'] or feed['url']}: {exc}")
            continue

        if result is None:
            continue

        now = datetime.now(timezone.utc).isoformat()
        title = result.title if result.title else feed.get("title")
        db.execute(
            _UPDATE_FEED_SQL,
            (title, result.site_url, result.etag,
             result.last_modified, now, feed["id"]),
        )
        total_new += _insert_entries(feed["id"], result.entries)

    parts = [
        f"Fetched {len(feeds_to_fetch)} feed(s): {total_new} new entries"
    ]
    if errors:
        parts.append(f"Errors ({len(errors)}): " + "; ".join(errors))
    return ". ".join(parts)
