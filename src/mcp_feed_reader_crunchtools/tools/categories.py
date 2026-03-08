"""Category management tools."""

from __future__ import annotations

import sqlite3
from typing import Any

from .. import database as db
from ..errors import CategoryNotFoundError, DuplicateCategoryError


async def list_categories() -> list[dict[str, Any]]:
    """List all categories with feed counts."""
    return db.query(
        """
        SELECT c.id, c.name, COUNT(f.id) AS feed_count
        FROM categories c
        LEFT JOIN feeds f ON f.category_id = c.id
        GROUP BY c.id, c.name
        ORDER BY c.name
        """
    )


async def create_category(name: str) -> dict[str, Any]:
    """Create a new category."""
    try:
        cat_id = db.execute("INSERT INTO categories (name) VALUES (?)", (name,))
    except sqlite3.IntegrityError as exc:
        raise DuplicateCategoryError(name) from exc
    row = db.query_one("SELECT * FROM categories WHERE id = ?", (cat_id,))
    assert row is not None
    return row


async def rename_category(category_id: int, name: str) -> dict[str, Any]:
    """Rename a category."""
    existing = db.query_one("SELECT id FROM categories WHERE id = ?", (category_id,))
    if not existing:
        raise CategoryNotFoundError(category_id)
    try:
        db.execute("UPDATE categories SET name = ? WHERE id = ?", (name, category_id))
    except sqlite3.IntegrityError as exc:
        raise DuplicateCategoryError(name) from exc
    row = db.query_one("SELECT * FROM categories WHERE id = ?", (category_id,))
    assert row is not None
    return row


async def delete_category(category_id: int) -> str:
    """Delete a category. Feeds in this category become uncategorized."""
    existing = db.query_one("SELECT name FROM categories WHERE id = ?", (category_id,))
    if not existing:
        raise CategoryNotFoundError(category_id)
    db.execute("DELETE FROM categories WHERE id = ?", (category_id,))
    return f"Deleted category: {existing['name']}"
