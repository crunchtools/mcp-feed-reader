"""Entry management tools."""

from __future__ import annotations

from typing import Any

from .. import database as db
from ..errors import EntryNotFoundError


async def list_entries(
    feed_id: int | None = None,
    category_id: int | None = None,
    unread_only: bool = True,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """List entries with optional filters."""
    conditions = []
    params: list[int | str] = []

    if feed_id is not None:
        conditions.append("e.feed_id = ?")
        params.append(feed_id)

    if category_id is not None:
        conditions.append("f.category_id = ?")
        params.append(category_id)

    if unread_only:
        conditions.append("e.is_read = 0")

    where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

    sql = (
        "SELECT e.id, e.feed_id, e.title, e.url, e.author, e.published,"
        " e.is_read, e.created_at, f.title AS feed_title"
        " FROM entries e JOIN feeds f ON e.feed_id = f.id"
    )
    if where_clause:
        sql += " " + where_clause
    sql += " ORDER BY e.published DESC NULLS LAST, e.created_at DESC"
    sql += " LIMIT ? OFFSET ?"
    return db.query(sql, (*params, limit, offset))


async def read_entry(entry_id: int) -> dict[str, Any]:
    """Get full content of an entry and mark it as read."""
    row = db.query_one(
        """
        SELECT e.*, f.title AS feed_title
        FROM entries e
        JOIN feeds f ON e.feed_id = f.id
        WHERE e.id = ?
        """,
        (entry_id,),
    )
    if not row:
        raise EntryNotFoundError(entry_id)

    if not row["is_read"]:
        db.execute("UPDATE entries SET is_read = 1 WHERE id = ?", (entry_id,))
        row = dict(row)
        row["is_read"] = 1

    return row


async def mark_read(
    entry_id: int | None = None,
    feed_id: int | None = None,
    all_entries: bool = False,
) -> str:
    """Mark entries as read by entry ID, feed ID, or all."""
    if entry_id is not None:
        existing = db.query_one("SELECT id FROM entries WHERE id = ?", (entry_id,))
        if not existing:
            raise EntryNotFoundError(entry_id)
        db.execute("UPDATE entries SET is_read = 1 WHERE id = ?", (entry_id,))
        return "Marked 1 entry as read"

    if feed_id is not None:
        db.execute(
            "UPDATE entries SET is_read = 1"
            " WHERE feed_id = ? AND is_read = 0",
            (feed_id,),
        )
        return f"Marked all unread entries in feed {feed_id} as read"

    if all_entries:
        db.execute("UPDATE entries SET is_read = 1 WHERE is_read = 0")
        return "Marked all entries as read"

    return "No action taken. Specify entry_id, feed_id, or all_entries=True."


async def mark_unread(entry_id: int) -> str:
    """Mark an entry as unread."""
    existing = db.query_one("SELECT id FROM entries WHERE id = ?", (entry_id,))
    if not existing:
        raise EntryNotFoundError(entry_id)
    db.execute("UPDATE entries SET is_read = 0 WHERE id = ?", (entry_id,))
    return "Marked entry as unread"


async def search_entries(query: str, limit: int = 50) -> list[dict[str, Any]]:
    """Full-text search across entry titles and content."""
    return db.query(
        """
        SELECT e.id, e.feed_id, e.title, e.url, e.author, e.published,
               e.is_read, f.title AS feed_title,
               snippet(entries_fts, 1, '<mark>', '</mark>', '...', 32) AS snippet
        FROM entries_fts
        JOIN entries e ON entries_fts.rowid = e.id
        JOIN feeds f ON e.feed_id = f.id
        WHERE entries_fts MATCH ?
        ORDER BY rank
        LIMIT ?
        """,
        (query, limit),
    )
