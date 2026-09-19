# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/) and this project adheres to
[Semantic Versioning](https://semver.org/).

Entries prior to 2026-09-19 are back-filled from GitHub Release notes (RT #1484).

## [Unreleased]

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
