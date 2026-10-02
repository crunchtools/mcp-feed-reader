# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/) and this project adheres to
[Semantic Versioning](https://semver.org/).

Entries prior to 2026-09-19 are back-filled from GitHub Release notes (RT #1484).

## [Unreleased]

### Changed

- Constitution is now a v1.18.0 manifest: it holds only what is specific to
  this repo; fleet and profile rules apply by reference.
- Constitution validation is pinned to the inherited release via
  `.github/workflows/constitution.yml`.
- Dependabot auto-merges GitHub Actions minor and patch updates.

## [0.4.0] - 2026-10-02

### Added
- The seven tools that change nothing publish `readOnlyHint: true`:
  `list_feeds`, `get_feed`, `list_entries`, `search_entries`,
  `list_categories`, `export_opml` and `get_stats`. A gateway uses the
  annotation to decide whether an invalid optional argument, such as the
  `feed_id: 0` some clients send as a placeholder, may be dropped or must
  refuse the call (crunchtools/mcp-trentina#335). `read_entry` is not
  annotated, because it marks the entry read.

## [0.3.0] - 2026-09-30

### Added
- `deploy/mcp-feeds-refresh.{service,timer}` — the systemd units that crawl
  feeds, with the README section explaining why a deployment without them is
  broken. Nothing in the server crawls on its own, and a stale cache reports
  as an empty feed rather than as an error: the daily briefing ran for days
  on 61 unfetched feeds with no failure anywhere to notice. The timer fires
  hourly plus once at 05:45, because a consumer that windows on publication
  time permanently loses anything published between the last crawl and its
  own run.
- A fetch that hits a rate limit (429), a gateway 5xx, or a dropped connection
  is retried with exponential backoff, up to three attempts in all. A definite
  answer — 404, 401, 304 — is still acted on at once. Reddit throttles per exit
  IP for a few seconds at a time, which used to cost a feed its whole crawl.

### Changed
- Documented `HTTP_PROXY`/`HTTPS_PROXY`/`NO_PROXY`, which httpx already
  honoured. They are the answer to a publisher that rate-limits your egress
  IP whatever User-Agent you send.

## [0.2.3] - 2026-09-26

### Changed
- Every ID parameter publishes `minimum: 1` in its tool schema (constitution
  mcp-server 1.5.0), so a gateway such as Trentina can tell `feed_id: 0`
  from a real ID and drop it before forwarding. An optional ID still maps a
  non-positive value to "not given" before the bound applies, so a direct
  `feed_id: 0` is served as before. A required ID of `0` is refused.
- Locked fastmcp moves from 3.1.0 to 4.0.10, the version the image already
  installs, so the tests exercise what ships.

### Fixed
- The image's `version` label said 0.2.1.

## [0.2.2] - 2026-09-26

### Fixed
- `refresh_feeds_tool`: a non-positive `feed_id` means "not given" (refresh
  all) instead of "Feed not found: 0".
- `list_entries_tool`: a non-positive `feed_id` or `category_id` means "not
  given", and a blank `published_after` / `published_before` means no bound.
- Both come from tool-calling models that fill every optional parameter with
  `0` or `""` (RT #1505).
- The fetcher User-Agent carries the package version instead of a stale 0.1.3.

## [0.2.1] - 2026-08-30

### Fixed
- ruff PLR0917 — date-window params (`since_days`, `published_after`,
  `published_before`) are now keyword-only. No behavior change from 0.2.0.

## [0.2.0] - 2026-08-30

### Added
- Optional `since_days`, `published_after`, `published_before` params on
  `list_entries_tool` for date-windowed queries. Filters on
  `datetime(COALESCE(published, created_at))` so null-published entries window by
  ingest time and mixed on-disk timestamp formats normalize correctly.
  Backward-compatible. Spec: `.specify/specs/001-entry-date-window/spec.md`.

## [0.1.3] - 2026-03-08

### Changed
- Wired Pydantic models into the tool runtime path — `FeedInput`, `CategoryInput`,
  `EntryListParams`, and `SearchParams` are now enforced at the top of each tool
  function. Constraints like `extra="forbid"`, `max_length`, and range limits
  (`ge`/`le`) are applied at runtime, not just in tests. Layer 2 (Input
  Validation) moves from 2/3 to 3/3, bringing the constitution scorecard to 23/24
  (Grade A).

### Fixed
- User-Agent version updated from `0.1.0` to `0.1.3`.

## [0.1.2] - 2026-03-08

### Fixed
- MCP Registry name in README for publishing. No functional changes.

## [0.1.1] - 2026-03-08

### Added
- Governance files: SECURITY.md, server.json, .pre-commit-config.yaml, issue
  templates.
- Constitution compliance: SecretStr pattern, all CI gates passing.

### Fixed
- Empty feed titles: when an RSS feed has an empty `<title>` element, fall back to
  the hostname from the feed URL.
- Container build: removed `mkdir /data`, which failed as non-root in the
  Hummingbird base image.
- All 27 Gourmand violations: named constants, match/case, inlined helpers,
  removed verbose comments.

## [0.1.0] - 2026-03-07

Initial tagged release. No GitHub Release was created for this tag, so no
authored release notes exist to back-fill from.
