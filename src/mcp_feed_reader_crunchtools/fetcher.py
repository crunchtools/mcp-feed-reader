"""Feed fetcher: downloads and parses RSS/Atom feeds."""

from __future__ import annotations

import contextlib
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import feedparser  # type: ignore[import-untyped]
import httpx

from .errors import FetchError

FETCH_TIMEOUT = 30
MAX_RESPONSE_SIZE = 10 * 1024 * 1024
USER_AGENT = (
    "mcp-feed-reader-crunchtools/0.1.0"
    " (+https://github.com/crunchtools/mcp-feed-reader)"
)


async def fetch_feed(
    url: str,
    etag: str | None = None,
    last_modified: str | None = None,
) -> FetchResult | None:
    """Fetch a feed URL and parse it.

    Returns None if the feed has not been modified (304).
    Raises FetchError on failure.
    """
    response = await _download(url, etag, last_modified)
    if response is None:
        return None

    parsed = feedparser.parse(response.text)
    if parsed.bozo and not parsed.entries:
        raise FetchError(url, f"Parse error: {parsed.bozo_exception}")

    title = parsed.feed.get("title", "").strip()
    if not title:
        title = urlparse(url).hostname or url

    return FetchResult(
        title=title,
        site_url=parsed.feed.get("link", ""),
        etag=response.headers.get("ETag"),
        last_modified=response.headers.get("Last-Modified"),
        entries=[_parse_entry(e) for e in parsed.entries],
    )


async def _download(
    url: str, etag: str | None, last_modified: str | None
) -> httpx.Response | None:
    """Download a feed URL, returning None on 304."""
    headers: dict[str, str] = {"User-Agent": USER_AGENT}
    if etag:
        headers["If-None-Match"] = etag
    if last_modified:
        headers["If-Modified-Since"] = last_modified

    try:
        async with httpx.AsyncClient(
            timeout=FETCH_TIMEOUT, follow_redirects=True, max_redirects=5,
        ) as client:
            response = await client.get(url, headers=headers)
    except httpx.HTTPError as exc:
        raise FetchError(url, str(exc)) from exc

    if response.status_code == 304:
        return None
    if response.status_code != 200:
        raise FetchError(url, f"HTTP {response.status_code}")
    if len(response.content) > MAX_RESPONSE_SIZE:
        raise FetchError(url, "Response exceeds 10MB limit")
    return response


def _parse_entry(entry: Any) -> dict[str, Any]:
    """Extract fields from a feedparser entry."""
    content = ""
    if hasattr(entry, "content") and entry.content:
        content = entry.content[0].get("value", "")
    elif hasattr(entry, "summary"):
        content = entry.summary or ""

    published = _parse_date(entry)
    guid = entry.get("id") or entry.get("link") or entry.get("title", "")

    return {
        "guid": guid,
        "title": entry.get("title", ""),
        "url": entry.get("link", ""),
        "author": entry.get("author", ""),
        "content": content,
        "published": published,
    }


def _parse_date(entry: Any) -> str | None:
    """Extract a published date from a feedparser entry."""
    for attr in ("published_parsed", "updated_parsed"):
        parsed_time = getattr(entry, attr, None)
        if parsed_time:
            with contextlib.suppress(TypeError, ValueError):
                dt = datetime(
                    parsed_time[0], parsed_time[1], parsed_time[2],
                    parsed_time[3], parsed_time[4], parsed_time[5],
                    tzinfo=timezone.utc,
                )
                return dt.isoformat()
    return None


class FetchResult:
    """Result of fetching and parsing a feed."""

    def __init__(
        self,
        title: str,
        site_url: str,
        etag: str | None,
        last_modified: str | None,
        entries: list[dict[str, Any]],
    ) -> None:
        self.title = title
        self.site_url = site_url
        self.etag = etag
        self.last_modified = last_modified
        self.entries = entries
