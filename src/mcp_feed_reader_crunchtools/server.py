"""MCP server registration for mcp-feed-reader-crunchtools."""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from .tools import (
    add_feed,
    create_category,
    delete_category,
    delete_feed,
    export_opml,
    fetch_feeds,
    get_feed,
    get_stats,
    import_opml,
    list_categories,
    list_entries,
    list_feeds,
    mark_read,
    mark_unread,
    read_entry,
    rename_category,
    search_entries,
)

mcp = FastMCP(
    "mcp-feed-reader-crunchtools",
    version="0.1.0",
    instructions=(
        "RSS/Atom feed reader MCP server with SQLite backend. "
        "Use add_feed to subscribe, fetch_feeds to pull new content, "
        "list_entries to see unread items, read_entry to view full content. "
        "Supports OPML import/export and full-text search."
    ),
)


# --- Feed Management ---


@mcp.tool()
async def add_feed_tool(url: str, category: str | None = None) -> dict[str, Any]:
    """Add an RSS/Atom feed by URL, optionally assign to a category.

    Args:
        url: Feed URL (RSS, Atom, or RDF)
        category: Category name (created if it does not exist)
    """
    return await add_feed(url, category)


@mcp.tool()
async def list_feeds_tool(category_id: int | None = None) -> list[dict[str, Any]]:
    """List all feeds with unread counts.

    Args:
        category_id: Filter by category ID (optional)
    """
    return await list_feeds(category_id)


@mcp.tool()
async def get_feed_tool(feed_id: int) -> dict[str, Any]:
    """Get details for a single feed including entry counts.

    Args:
        feed_id: Feed ID
    """
    return await get_feed(feed_id)


@mcp.tool()
async def delete_feed_tool(feed_id: int) -> str:
    """Remove a feed and all its entries.

    Args:
        feed_id: Feed ID to delete
    """
    return await delete_feed(feed_id)


@mcp.tool()
async def fetch_feeds_tool(feed_id: int | None = None) -> str:
    """Fetch new entries for all feeds or a specific feed.

    Args:
        feed_id: Specific feed ID to fetch (optional, fetches all if omitted)
    """
    return await fetch_feeds(feed_id)


# --- Entry Management ---


@mcp.tool()
async def list_entries_tool(
    feed_id: int | None = None,
    category_id: int | None = None,
    unread_only: bool = True,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """List entries with optional filters.

    Args:
        feed_id: Filter by feed ID
        category_id: Filter by category ID
        unread_only: Show only unread entries (default: True)
        limit: Max entries to return (1-500, default: 50)
        offset: Pagination offset (default: 0)
    """
    return await list_entries(feed_id, category_id, unread_only, limit, offset)


@mcp.tool()
async def read_entry_tool(entry_id: int) -> dict[str, Any]:
    """Get full content of an entry (auto-marks as read).

    Args:
        entry_id: Entry ID
    """
    return await read_entry(entry_id)


@mcp.tool()
async def mark_read_tool(
    entry_id: int | None = None,
    feed_id: int | None = None,
    all_entries: bool = False,
) -> str:
    """Mark entries as read.

    Args:
        entry_id: Mark a single entry as read
        feed_id: Mark all entries in a feed as read
        all_entries: Mark ALL entries as read (use with caution)
    """
    return await mark_read(entry_id, feed_id, all_entries)


@mcp.tool()
async def mark_unread_tool(entry_id: int) -> str:
    """Mark an entry as unread.

    Args:
        entry_id: Entry ID
    """
    return await mark_unread(entry_id)


@mcp.tool()
async def search_entries_tool(query: str, limit: int = 50) -> list[dict[str, Any]]:
    """Full-text search across entry titles and content.

    Args:
        query: Search query (FTS5 syntax supported)
        limit: Max results (1-500, default: 50)
    """
    return await search_entries(query, limit)


# --- Category Management ---


@mcp.tool()
async def list_categories_tool() -> list[dict[str, Any]]:
    """List all categories with feed counts."""
    return await list_categories()


@mcp.tool()
async def create_category_tool(name: str) -> dict[str, Any]:
    """Create a new category.

    Args:
        name: Category name
    """
    return await create_category(name)


@mcp.tool()
async def rename_category_tool(category_id: int, name: str) -> dict[str, Any]:
    """Rename a category.

    Args:
        category_id: Category ID
        name: New name
    """
    return await rename_category(category_id, name)


@mcp.tool()
async def delete_category_tool(category_id: int) -> str:
    """Delete a category. Feeds in this category become uncategorized.

    Args:
        category_id: Category ID to delete
    """
    return await delete_category(category_id)


# --- Import/Export ---


@mcp.tool()
async def import_opml_tool(file_path: str) -> str:
    """Import feeds from an OPML file, creating categories from outline groups.

    Args:
        file_path: Path to the OPML file
    """
    return await import_opml(file_path)


@mcp.tool()
async def export_opml_tool() -> str:
    """Export all feeds as OPML XML string."""
    return await export_opml()


@mcp.tool()
async def get_stats_tool() -> dict[str, Any]:
    """Get dashboard stats: total feeds, unread count, entries per category."""
    return await get_stats()
