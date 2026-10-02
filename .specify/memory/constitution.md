# mcp-feed-reader-crunchtools Constitution

> **Version:** 1.1.0
> **Ratified:** 2026-03-07
> **Amended:** 2026-10-02
> **Status:** Active
> **Inherits:** [crunchtools/constitution](https://github.com/crunchtools/constitution) v1.18.0
> **Profile:** MCP Server

This file holds what is specific to mcp-feed-reader. The fleet rules and the
MCP Server profile (five-layer security model, two-layer tools, distribution
channels, transports, quality gates, Gourmand) apply at the inherited version
and are checked against this repo's files by `constitution.yml`. They are not
restated here.

## Security Model Specifics

- **Credentials:** none. The server reads public RSS/Atom feeds and needs no
  service account; the `SecretStr` pattern in `config.py` is there if one is
  ever added.
- **Input limits:** Pydantic models with `extra="forbid"`; feed URLs must be
  `http://` or `https://` and at most 2048 characters, names 200, search
  queries 500, page size 500, `since_days` 366. An OPML import without a
  `<body>` element is rejected.
- **Feed fetching:** TLS certificates are validated, requests time out after
  30s, responses are capped at 10MB, at most 5 redirects are followed, and
  every request carries an identifying User-Agent. Transient failures (429,
  500, 502, 503, 504, dropped connections) are retried with exponential
  backoff, three attempts in all.
- **Surface:** filesystem access is limited to the SQLite database and the
  local OPML file passed to `import_opml`; no shell execution or code
  evaluation. Feed HTML is parsed by feedparser, whose default sanitizer
  runs before storage.

## Self-Contained Storage

The server works without any external service:

- `FEED_READER_DB` sets the SQLite path (default
  `~/.local/share/mcp-feed-reader/feeds.db`; `/data/feeds.db` in the
  container, persisted on a volume mounted at `/data`).
- The database is created on first run; an FTS5 full-text index is kept in
  sync by triggers.

## Scheduled Crawl

`deploy/` ships the `mcp-feeds-refresh` service and timer. The service runs
`--fetch` inside the running container (`podman exec`) so the database keeps
the SELinux category of the process that owns it; the data directory is never
bind-mounted into a second container with `:Z`. The timer fires hourly plus
once at 05:45, so consumers that window entries on publication time for a
06:00 report do not lose entries published after the last hourly crawl.

## Tests Use In-Memory SQLite

Instead of mocked HTTP, tool tests run against a fresh `:memory:` SQLite
database per test, seeded as needed, and call the tool function directly
rather than the `_tool` wrapper. Test classes: `TestFeedTools`,
`TestEntryTools`, `TestCategoryTools`, `TestImportExportTools`,
`TestErrorHandling`. `test_tool_count` is updated whenever a tool is added or
removed.

## Instance

| Context | Name |
|---------|------|
| GitHub repo | `crunchtools/mcp-feed-reader` |
| PyPI package | `mcp-feed-reader-crunchtools` |
| Container image | `quay.io/crunchtools/mcp-feed-reader` |
| systemd service | `mcp-feed-reader.service` |
| HTTP port | 8018 |

## History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-03-07 | Initial constitution |
| 1.0.1 | 2026-03-16 | Add Section VI (Container Conventions); renumber VI-VIII to VII-IX |
| 1.0.2 | 2026-09-25 | Inherit constitution v1.17.0 (Gatehouse gates) |
| 1.1.0 | 2026-10-02 | Manifest under constitution v1.18.0: profile restatement removed, feed-reader specifics kept; fetch and filesystem rules corrected to match the code |
