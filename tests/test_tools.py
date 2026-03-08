"""Tests for mcp-feed-reader-crunchtools tools."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

import pytest

from mcp_feed_reader_crunchtools import database as db_mod

if TYPE_CHECKING:
    import sqlite3
from mcp_feed_reader_crunchtools.fetcher import FetchResult
from mcp_feed_reader_crunchtools.server import mcp
from mcp_feed_reader_crunchtools.tools.categories import (
    create_category,
    delete_category,
    list_categories,
    rename_category,
)
from mcp_feed_reader_crunchtools.tools.entries import (
    list_entries,
    mark_read,
    mark_unread,
    read_entry,
    search_entries,
)
from mcp_feed_reader_crunchtools.tools.feeds import (
    add_feed,
    delete_feed,
    fetch_feeds,
    get_feed,
    list_feeds,
)
from mcp_feed_reader_crunchtools.tools.opml import export_opml, get_stats, import_opml

EXPECTED_TOOL_COUNT = 17


def _mock_fetch_result() -> FetchResult:
    """Create a mock FetchResult for testing."""
    return FetchResult(
        title="Test Feed",
        site_url="https://example.com",
        etag='"abc123"',
        last_modified="Mon, 01 Jan 2026 00:00:00 GMT",
        entries=[
            {
                "guid": "entry-1",
                "title": "First Post",
                "url": "https://example.com/post-1",
                "author": "Author",
                "content": "<p>Content of the first post</p>",
                "published": "2026-01-01T00:00:00+00:00",
            },
            {
                "guid": "entry-2",
                "title": "Second Post",
                "url": "https://example.com/post-2",
                "author": "Author",
                "content": "<p>Content of the second post</p>",
                "published": "2026-01-02T00:00:00+00:00",
            },
        ],
    )


class TestToolCount:
    @pytest.mark.asyncio
    async def test_tool_count(self) -> None:
        tools = await mcp.list_tools()
        assert len(tools) == EXPECTED_TOOL_COUNT


class TestCategoryTools:
    @pytest.mark.asyncio
    async def test_create_category(self, in_memory_db: sqlite3.Connection) -> None:
        result = await create_category("Tech")
        assert result["name"] == "Tech"
        assert result["id"] >= 1

    @pytest.mark.asyncio
    async def test_list_categories(self, in_memory_db: sqlite3.Connection) -> None:
        await create_category("Tech")
        await create_category("Finance")
        cats = await list_categories()
        assert len(cats) == 2
        assert cats[0]["name"] == "Finance"
        assert cats[1]["name"] == "Tech"

    @pytest.mark.asyncio
    async def test_rename_category(self, in_memory_db: sqlite3.Connection) -> None:
        cat = await create_category("Tech")
        renamed = await rename_category(cat["id"], "Technology")
        assert renamed["name"] == "Technology"

    @pytest.mark.asyncio
    async def test_delete_category(self, in_memory_db: sqlite3.Connection) -> None:
        cat = await create_category("Tech")
        result = await delete_category(cat["id"])
        assert "Deleted" in result
        cats = await list_categories()
        assert len(cats) == 0

    @pytest.mark.asyncio
    async def test_duplicate_category(self, in_memory_db: sqlite3.Connection) -> None:
        await create_category("Tech")
        from mcp_feed_reader_crunchtools.errors import DuplicateCategoryError

        with pytest.raises(DuplicateCategoryError):
            await create_category("Tech")


class TestFeedTools:
    @pytest.mark.asyncio
    async def test_add_feed(self, in_memory_db: sqlite3.Connection) -> None:
        with patch(
            "mcp_feed_reader_crunchtools.tools.feeds.fetch_feed",
            new_callable=AsyncMock,
            return_value=_mock_fetch_result(),
        ):
            feed = await add_feed("https://example.com/feed.xml", "Tech")
        assert feed["url"] == "https://example.com/feed.xml"
        assert feed["title"] == "Test Feed"

    @pytest.mark.asyncio
    async def test_list_feeds(self, in_memory_db: sqlite3.Connection) -> None:
        with patch(
            "mcp_feed_reader_crunchtools.tools.feeds.fetch_feed",
            new_callable=AsyncMock,
            return_value=_mock_fetch_result(),
        ):
            await add_feed("https://example.com/feed.xml")
        feeds = await list_feeds()
        assert len(feeds) == 1
        assert feeds[0]["total_entries"] == 2

    @pytest.mark.asyncio
    async def test_get_feed(self, in_memory_db: sqlite3.Connection) -> None:
        with patch(
            "mcp_feed_reader_crunchtools.tools.feeds.fetch_feed",
            new_callable=AsyncMock,
            return_value=_mock_fetch_result(),
        ):
            feed = await add_feed("https://example.com/feed.xml")
        detail = await get_feed(feed["id"])
        assert detail["unread_count"] == 2

    @pytest.mark.asyncio
    async def test_delete_feed(self, in_memory_db: sqlite3.Connection) -> None:
        with patch(
            "mcp_feed_reader_crunchtools.tools.feeds.fetch_feed",
            new_callable=AsyncMock,
            return_value=_mock_fetch_result(),
        ):
            feed = await add_feed("https://example.com/feed.xml")
        result = await delete_feed(feed["id"])
        assert "Deleted" in result
        feeds = await list_feeds()
        assert len(feeds) == 0

    @pytest.mark.asyncio
    async def test_fetch_feeds(self, in_memory_db: sqlite3.Connection) -> None:
        db_mod.execute(
            "INSERT INTO feeds (url, title) VALUES (?, ?)",
            ("https://example.com/feed.xml", "Test"),
        )
        with patch(
            "mcp_feed_reader_crunchtools.tools.feeds.fetch_feed",
            new_callable=AsyncMock,
            return_value=_mock_fetch_result(),
        ):
            result = await fetch_feeds()
        assert "2 new entries" in result

    @pytest.mark.asyncio
    async def test_duplicate_feed(self, in_memory_db: sqlite3.Connection) -> None:
        with patch(
            "mcp_feed_reader_crunchtools.tools.feeds.fetch_feed",
            new_callable=AsyncMock,
            return_value=_mock_fetch_result(),
        ):
            await add_feed("https://example.com/feed.xml")

        from mcp_feed_reader_crunchtools.errors import DuplicateFeedError

        with pytest.raises(DuplicateFeedError), patch(
            "mcp_feed_reader_crunchtools.tools.feeds.fetch_feed",
            new_callable=AsyncMock,
            return_value=_mock_fetch_result(),
        ):
            await add_feed("https://example.com/feed.xml")


class TestEntryTools:
    @pytest.fixture(autouse=True)
    async def _setup_entries(self, in_memory_db: sqlite3.Connection) -> None:
        """Seed the database with a feed and entries."""
        with patch(
            "mcp_feed_reader_crunchtools.tools.feeds.fetch_feed",
            new_callable=AsyncMock,
            return_value=_mock_fetch_result(),
        ):
            await add_feed("https://example.com/feed.xml")

    @pytest.mark.asyncio
    async def test_list_entries_unread(self) -> None:
        entries = await list_entries(unread_only=True)
        assert len(entries) == 2
        assert all(e["is_read"] == 0 for e in entries)

    @pytest.mark.asyncio
    async def test_read_entry(self) -> None:
        entries = await list_entries()
        entry = await read_entry(entries[0]["id"])
        assert entry["is_read"] == 1
        assert "content" in entry

    @pytest.mark.asyncio
    async def test_mark_read_single(self) -> None:
        entries = await list_entries()
        result = await mark_read(entry_id=entries[0]["id"])
        assert "1 entry" in result
        unread = await list_entries(unread_only=True)
        assert len(unread) == 1

    @pytest.mark.asyncio
    async def test_mark_read_all(self) -> None:
        result = await mark_read(all_entries=True)
        assert "all" in result.lower()
        unread = await list_entries(unread_only=True)
        assert len(unread) == 0

    @pytest.mark.asyncio
    async def test_mark_unread(self) -> None:
        entries = await list_entries()
        await read_entry(entries[0]["id"])
        result = await mark_unread(entries[0]["id"])
        assert "unread" in result.lower()

    @pytest.mark.asyncio
    async def test_search_entries(self) -> None:
        results = await search_entries("first post")
        assert len(results) >= 1
        assert results[0]["title"] == "First Post"


class TestOPMLTools:
    @pytest.mark.asyncio
    async def test_import_opml(self, in_memory_db: sqlite3.Connection) -> None:
        opml_content = """<?xml version="1.0" encoding="UTF-8"?>
<opml version="1.0">
  <head><title>Test</title></head>
  <body>
    <outline text="Tech" title="Tech">
      <outline type="rss" text="Example" xmlUrl="https://example.com/feed.xml"/>
      <outline type="rss" text="Other" xmlUrl="https://other.com/feed.xml"/>
    </outline>
  </body>
</opml>"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".opml", delete=False) as f:
            f.write(opml_content)
            path = f.name

        result = await import_opml(path)
        assert "2 feeds" in result.lower()

        feeds = await list_feeds()
        assert len(feeds) == 2

        cats = await list_categories()
        assert len(cats) == 1
        assert cats[0]["name"] == "Tech"

        Path(path).unlink()

    @pytest.mark.asyncio
    async def test_export_opml(self, in_memory_db: sqlite3.Connection) -> None:
        await create_category("Tech")
        db_mod.execute(
            "INSERT INTO feeds (url, title, category_id) VALUES (?, ?, ?)",
            ("https://example.com/feed.xml", "Example Feed", 1),
        )
        xml = await export_opml()
        assert "example.com/feed.xml" in xml
        assert "Tech" in xml

    @pytest.mark.asyncio
    async def test_get_stats(self, in_memory_db: sqlite3.Connection) -> None:
        with patch(
            "mcp_feed_reader_crunchtools.tools.feeds.fetch_feed",
            new_callable=AsyncMock,
            return_value=_mock_fetch_result(),
        ):
            await add_feed("https://example.com/feed.xml", "Tech")
        stats = await get_stats()
        assert stats["total_feeds"] == 1
        assert stats["total_entries"] == 2
        assert stats["unread_entries"] == 2


class TestErrorHandling:
    @pytest.mark.asyncio
    async def test_feed_not_found(self, in_memory_db: sqlite3.Connection) -> None:
        from mcp_feed_reader_crunchtools.errors import FeedNotFoundError

        with pytest.raises(FeedNotFoundError):
            await get_feed(999)

    @pytest.mark.asyncio
    async def test_entry_not_found(self, in_memory_db: sqlite3.Connection) -> None:
        from mcp_feed_reader_crunchtools.errors import EntryNotFoundError

        with pytest.raises(EntryNotFoundError):
            await read_entry(999)

    @pytest.mark.asyncio
    async def test_category_not_found(self, in_memory_db: sqlite3.Connection) -> None:
        from mcp_feed_reader_crunchtools.errors import CategoryNotFoundError

        with pytest.raises(CategoryNotFoundError):
            await rename_category(999, "New Name")
