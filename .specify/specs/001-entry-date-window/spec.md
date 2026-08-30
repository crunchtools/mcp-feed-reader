# Spec 001 — Entry date-window filtering on `list_entries_tool`

> **Status:** Proposed
> **Author:** Scott McCarty (@fatherlinux) / Josui
> **Created:** 2026-08-30
> **Target version:** 0.2.0 (MINOR — backward-compatible new functionality, SemVer)
> **Profile:** MCP Server · **Constitution:** mcp-feed-reader-crunchtools v1.0.1 (inherits crunchtools/constitution v1.0.0)

---

## 1. Problem

`list_entries_tool` filters by feed, category, and read-state, but has **no way to bound results by date**. The only lever for "the last N days" is `limit` (max 500) plus client-side date filtering after the rows come back.

This is expensive for date-windowed consumers. The concrete driver is Metsuke's `weekend-report` (a Saturday RSS round-up over the trailing 7 days): to be sure it covers the window it must pull large `limit` batches across every in-scope category and discard the out-of-window rows in-agent. One such sweep returned a **366 KB tool result (~90 K tokens) of metadata**, most of it thrown away. The current mitigation is a hand-tuned per-category `limit` allocation in the gather prompt — a guess at "how many rows ≈ a week," which under-pulls on a busy week and over-pulls on a quiet one.

The right fix is at the data layer: let the query return exactly the window.

## 2. Goals

- Add optional date-window parameters to `list_entries_tool` so callers can request only entries within a time range.
- Preserve the tool's existing semantics exactly when the new params are omitted (backward compatible).
- Handle the two **different on-disk timestamp formats** correctly (see §5).
- Keep the change small: one tool, its Pydantic model, its SQL, and tests. No schema migration.

## 3. Non-goals

- No new tool. This extends `list_entries_tool` only. (`search_entries` may adopt the same params later; out of scope here.)
- No change to `refresh_feeds_tool`, crawling, or the systemd refresh timer.
- No re-indexing or DB schema change. `published` and `created_at` already exist on `entries`.
- Not solving feed staleness (separate concern: no standing refresh timer on lotor — tracked elsewhere).

## 4. Proposed interface

Add three optional parameters to `list_entries_tool` and `EntryListParams`:

| Param | Type | Default | Meaning |
|-------|------|---------|---------|
| `since_days` | `int \| None` | `None` | Convenience: only entries dated within the last N days (relative to now, UTC). `ge=1, le=366`. |
| `published_after` | `str \| None` | `None` | Absolute lower bound, ISO-8601 (e.g. `2026-08-23` or `2026-08-23T00:00:00Z`). Inclusive. |
| `published_before` | `str \| None` | `None` | Absolute upper bound, ISO-8601. Inclusive. |

**Rules:**
- All three optional; omitting all of them reproduces today's behavior byte-for-byte.
- `since_days` is a shorthand and is **mutually exclusive** with `published_after`/`published_before`. If `since_days` is combined with either absolute bound, raise a `UserError` (Pydantic model validator) — do not silently pick one.
- `published_after`/`published_before` may be used together (a closed range) or individually (open-ended).
- Invalid/unparseable timestamp strings raise a `UserError` with a clear message, never a 500.
- Bound the effective date string server-side (max length, `extra="forbid"` already enforced on the model).

Docstring must state which timestamp field is used and the null-fallback behavior (§5) so an agent caller reasons about it correctly.

## 5. The timestamp-format gotcha (implementation-critical)

The two columns are **not** stored in the same textual format and are **not** lexicographically comparable to each other or to a naive input string:

- `entries.published TEXT` — nullable; feed-supplied ISO-8601 **with `T` separator and a timezone offset**, e.g. `2026-08-30T09:03:00+00:00`. Many feeds emit `NULL`, garbage, or backdated values.
- `entries.created_at TEXT NOT NULL DEFAULT (datetime('now'))` — crawler ingest time, format `YYYY-MM-DD HH:MM:SS` (space separator, implicit UTC), e.g. `2026-08-30 10:51:08`.

Therefore:

1. **Filter on `COALESCE(e.published, e.created_at)`** — mirrors the existing `ORDER BY e.published DESC NULLS LAST, e.created_at DESC`, so an entry with null/absent `published` still falls into the window by its ingest time rather than vanishing. This matches how the report semantically wants "what showed up this week" while honoring real publish dates when present.
2. **Normalize both sides with SQLite `datetime()`** in the WHERE clause — never raw string compare. `datetime()` parses the `T` separator and the `+HH:MM`/`Z` offset and returns canonical `YYYY-MM-DD HH:MM:SS` in UTC, making the space-separated `created_at` and the offset-bearing `published` directly comparable. Compute the bound in Python (UTC) and pass it as a normalized string, e.g.:

   ```sql
   -- lower bound (since_days or published_after)
   AND datetime(COALESCE(e.published, e.created_at)) >= datetime(?)
   -- upper bound (published_before)
   AND datetime(COALESCE(e.published, e.created_at)) <= datetime(?)
   ```

   For `since_days`, compute `datetime.now(UTC) - timedelta(days=since_days)` and format as `%Y-%m-%d %H:%M:%S`. For the absolute params, parse the caller string (accept date-only and full ISO-8601), reject on failure.

3. Guard against a `datetime()` returning `NULL` for a malformed stored value — such a row simply falls outside any bound (SQLite comparisons against NULL are NULL/false), which is acceptable and safe.

## 6. Behavior examples

- `list_entries_tool(category_id=1, since_days=7, unread_only=False, limit=500)` → all Professional-category entries dated in the last 7 days, read or unread, newest first.
- `list_entries_tool(published_after="2026-08-23", published_before="2026-08-30")` → closed one-week window across all feeds.
- `list_entries_tool(since_days=7, published_after="2026-08-23")` → `UserError` (mutually exclusive).
- `list_entries_tool(limit=50)` → unchanged from today.

## 7. Testing (constitution §III — mocked, no live calls)

Add to the entries test suite:
- Boundary inclusion/exclusion: an entry exactly at the bound is included; one just outside is excluded.
- **Null-`published` fallback:** an entry with `published IS NULL` is windowed by `created_at`.
- **Mixed-format normalization:** rows with offset-bearing `published` and space-format `created_at` both compare correctly against the bound (the core gotcha — assert an offset-bearing row and a null-published row are both correctly in/out).
- `since_days` ⊕ absolute-bounds mutual-exclusion raises `UserError`.
- Unparseable `published_after` raises `UserError`.
- Composition: date window + `category_id` + `limit`/`offset` together.
- `test_tool_count` unchanged (no new tool); update the `list_entries_tool` signature test.

## 8. Rollout

1. Implement in `models.py` (params + validator), `tools/entries.py` (SQL), `server.py` (tool signature + docstring).
2. Five quality gates in order: `ruff` → `mypy` → `pytest` → `gourmand --full .` → `podman build`.
3. Bump version in all four locations (pyproject, `server.py` FastMCP ctor, `__init__.py`, `server.json`), tag `v0.2.0`, push → CI publishes PyPI + dual-push Quay/GHCR.
4. Deploy to lotor: pull `quay.io/crunchtools/mcp-feeds` (canonical — never GHCR), restart the unit.
5. **Refresh the gateway tool manifest** — after redeploy, `reconnect_backend_tool(backend="feeds")` then `/mcp` reconnect the client. The gateway caches backend tool schemas in SQLite; a restart alone serves the stale manifest and the new params won't appear. `profiles.yaml` `tools_allow` is unchanged (same tool name).

## 9. Downstream follow-up (not in this repo)

Once shipped, simplify Metsuke's `weekend-report` gather prompt: replace the per-category `limit` allocation (60/45/45/20/15/15) with `since_days=7` plus a modest safety `limit`, and drop the "keep only in-window entries" client-side filtering. That converts the trailing-week sweep from a token-heavy guess into an exact query, and the same param serves the planned consolidated Evening report (RT #1469).
