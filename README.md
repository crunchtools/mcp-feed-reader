# mcp-feed-reader-crunchtools

Secure MCP server for RSS/Atom feed reading with SQLite backend.

<!-- mcp-name: io.github.crunchtools/feed-reader -->

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
| `HTTP_PROXY` / `HTTPS_PROXY` / `NO_PROXY` | (none) | Standard httpx proxy variables, honoured for every feed fetch. Useful when a publisher rate-limits your egress IP — Reddit returns 429 to datacentre ranges regardless of User-Agent |

## Tools (17)

### Feed Management
- `add_feed_tool` — Add an RSS/Atom feed by URL
- `list_feeds_tool` — List all feeds with unread counts
- `get_feed_tool` — Get feed details
- `delete_feed_tool` — Remove a feed
- `refresh_feeds_tool` — Crawl feed sources for new content (slow, prefer systemd timer)

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

Nothing in the server crawls on its own. `list_entries_tool` and friends read a
cache; if no one calls `--fetch`, that cache goes stale and every reader sees an
empty feed with no error anywhere. **A deployment without a crawl trigger is a
broken deployment** — this bit the daily briefing, which reported "no news" for
days while all 61 feeds sat unfetched.

```bash
# Fetch all feeds via CLI
mcp-feed-reader-crunchtools --fetch
```

### systemd timer (recommended)

`deploy/` ships the two units used in production. Copy them to
`/etc/systemd/system/`, adjust the container name in the service if yours
differs, then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now mcp-feeds-refresh.timer
```

The service runs `--fetch` *inside* the running container
(`podman exec`), so the database keeps the SELinux category of the process that
owns it. Do not bind-mount the data directory into a second container with
`:Z` to run the crawl — that relabels the volume and locks the live server out.

The timer fires hourly, plus once at 05:45. That second entry is not
redundant: consumers window entries on publication time, so an entry published
between the last crawl and a 06:00 report is missing from that report *and*
already older than the next day's window start — it is lost for good. Any
consumer on a fixed schedule wants a crawl shortly before it.

Feeds are fetched conditionally (ETag / `If-Modified-Since`), and a rate limit,
gateway 5xx, or dropped connection is retried three times with exponential
backoff before the feed is recorded as failed.

## License

AGPL-3.0-or-later
