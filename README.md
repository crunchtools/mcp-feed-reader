# mcp-feed-reader-crunchtools

Secure MCP server for RSS/Atom feed reading with SQLite backend.

<!-- mcp-name: mcp-feed-reader-crunchtools -->

## Installation

### uvx (recommended)
```bash
uvx mcp-feed-reader-crunchtools
```

### pip
```bash
pip install mcp-feed-reader-crunchtools
```

### Container
```bash
podman run -v feedreader-data:/data quay.io/crunchtools/mcp-feed-reader
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `FEED_READER_DB` | `~/.local/share/mcp-feed-reader/feeds.db` | SQLite database path |

## Tools (17)

### Feed Management
- `add_feed_tool` — Add an RSS/Atom feed by URL
- `list_feeds_tool` — List all feeds with unread counts
- `get_feed_tool` — Get feed details
- `delete_feed_tool` — Remove a feed
- `fetch_feeds_tool` — Fetch new entries

### Entry Management
- `list_entries_tool` — List entries (filterable, paginated)
- `read_entry_tool` — Read full entry content (auto-marks read)
- `mark_read_tool` — Mark entries as read
- `mark_unread_tool` — Mark entry as unread
- `search_entries_tool` — Full-text search (FTS5)

### Category Management
- `list_categories_tool` — List categories with counts
- `create_category_tool` — Create category
- `rename_category_tool` — Rename category
- `delete_category_tool` — Delete category

### Import/Export
- `import_opml_tool` — Import from OPML file
- `export_opml_tool` — Export as OPML
- `get_stats_tool` — Dashboard stats

## Background Fetching

```bash
# Fetch all feeds via CLI
mcp-feed-reader-crunchtools --fetch
```

## License

AGPL-3.0-or-later
