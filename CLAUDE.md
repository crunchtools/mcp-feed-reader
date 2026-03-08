# mcp-feed-reader-crunchtools

RSS/Atom feed reader MCP server with SQLite backend.

## Quick Start

```bash
uv sync --all-extras
uv run mcp-feed-reader-crunchtools
```

## Environment Variables

- `FEED_READER_DB` — SQLite database path (default: ~/.local/share/mcp-feed-reader/feeds.db)

## Tools (17)

### Feed Management (5)
- add_feed_tool, list_feeds_tool, get_feed_tool, delete_feed_tool, fetch_feeds_tool

### Entry Management (5)
- list_entries_tool, read_entry_tool, mark_read_tool, mark_unread_tool, search_entries_tool

### Category Management (4)
- list_categories_tool, create_category_tool, rename_category_tool, delete_category_tool

### Import/Export (3)
- import_opml_tool, export_opml_tool, get_stats_tool

## Development

```bash
uv run ruff check src tests    # Lint
uv run mypy src                # Type check
uv run pytest -v               # Test
gourmand --full .              # Slop detection
podman build -f Containerfile . # Container
```

## Architecture

- `database.py` — SQLite with FTS5 (replaces client.py)
- `fetcher.py` — httpx + feedparser for feed fetching
- `tools/` — Two-layer: pure functions called by server.py wrappers
- `--fetch` CLI mode for systemd timer background fetching
