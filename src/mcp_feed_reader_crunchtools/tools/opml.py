"""OPML import/export and stats tools."""

from __future__ import annotations

import sqlite3
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from .. import database as db
from ..errors import FeedReaderError


async def import_opml(file_path: str) -> str:
    """Import feeds from an OPML file, creating categories from outline groups."""
    path = Path(file_path).expanduser()
    if not path.exists():
        raise FeedReaderError(f"File not found: {file_path}")

    tree = ET.parse(path)  # noqa: S314 — OPML files are local user-provided files
    root = tree.getroot()
    body = root.find("body")
    if body is None:
        raise FeedReaderError("Invalid OPML: no <body> element")

    added = 0
    skipped = 0

    for outline in body:
        category_name = outline.get("text") or outline.get("title")
        xml_url = outline.get("xmlUrl")

        if xml_url:
            _import_feed(xml_url, None)
            added += 1
            continue

        if category_name:
            cat_id = _ensure_category(category_name)
            for child in outline:
                child_url = child.get("xmlUrl")
                if child_url:
                    if _import_feed(child_url, cat_id):
                        added += 1
                    else:
                        skipped += 1

    return f"Imported {added} feeds, skipped {skipped} duplicates"


def _ensure_category(name: str) -> int:
    """Get or create a category by name, return its ID."""
    row = db.query_one("SELECT id FROM categories WHERE name = ?", (name,))
    if row:
        return int(row["id"])
    return db.execute("INSERT INTO categories (name) VALUES (?)", (name,))


def _import_feed(url: str, category_id: int | None) -> bool:
    """Insert a feed, return True if added, False if duplicate."""
    try:
        db.execute(
            "INSERT INTO feeds (url, category_id) VALUES (?, ?)",
            (url, category_id),
        )
    except sqlite3.IntegrityError:
        return False
    return True


async def export_opml() -> str:
    """Export all feeds as OPML XML string."""
    opml = ET.Element("opml", version="1.0")
    head = ET.SubElement(opml, "head")
    ET.SubElement(head, "title").text = "mcp-feed-reader-crunchtools export"
    body = ET.SubElement(opml, "body")

    categories = db.query(
        "SELECT id, name FROM categories ORDER BY name"
    )

    uncategorized = db.query(
        "SELECT url, title, site_url FROM feeds WHERE category_id IS NULL ORDER BY title"
    )

    for feed in uncategorized:
        attrs: dict[str, str] = {"type": "rss", "xmlUrl": feed["url"]}
        if feed["title"]:
            attrs["text"] = feed["title"]
            attrs["title"] = feed["title"]
        if feed["site_url"]:
            attrs["htmlUrl"] = feed["site_url"]
        ET.SubElement(body, "outline", attrib=attrs)

    for cat in categories:
        cat_outline = ET.SubElement(body, "outline", text=cat["name"], title=cat["name"])
        feeds = db.query(
            "SELECT url, title, site_url FROM feeds WHERE category_id = ? ORDER BY title",
            (cat["id"],),
        )
        for feed in feeds:
            attrs = {"type": "rss", "xmlUrl": feed["url"]}
            if feed["title"]:
                attrs["text"] = feed["title"]
                attrs["title"] = feed["title"]
            if feed["site_url"]:
                attrs["htmlUrl"] = feed["site_url"]
            ET.SubElement(cat_outline, "outline", attrib=attrs)

    return ET.tostring(opml, encoding="unicode", xml_declaration=True)


async def get_stats() -> dict[str, Any]:
    """Get dashboard stats: total feeds, unread count, entries per category."""
    total_feeds = db.query_one("SELECT COUNT(*) AS count FROM feeds")
    total_entries = db.query_one("SELECT COUNT(*) AS count FROM entries")
    unread_entries = db.query_one("SELECT COUNT(*) AS count FROM entries WHERE is_read = 0")
    last_fetch = db.query_one(
        "SELECT MAX(last_fetched) AS last_fetched FROM feeds"
    )

    per_category = db.query(
        """
        SELECT COALESCE(c.name, 'Uncategorized') AS category,
               COUNT(DISTINCT f.id) AS feed_count,
               COUNT(e.id) AS entry_count,
               SUM(CASE WHEN e.is_read = 0 THEN 1 ELSE 0 END) AS unread_count
        FROM feeds f
        LEFT JOIN categories c ON f.category_id = c.id
        LEFT JOIN entries e ON e.feed_id = f.id
        GROUP BY COALESCE(c.name, 'Uncategorized')
        ORDER BY category
        """
    )

    return {
        "total_feeds": total_feeds["count"] if total_feeds else 0,
        "total_entries": total_entries["count"] if total_entries else 0,
        "unread_entries": unread_entries["count"] if unread_entries else 0,
        "last_fetch": last_fetch["last_fetched"] if last_fetch else None,
        "per_category": per_category,
    }
