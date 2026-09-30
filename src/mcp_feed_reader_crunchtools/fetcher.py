"""Feed fetcher: downloads and parses RSS/Atom feeds."""

from __future__ import annotations

import asyncio
import contextlib
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import feedparser
import httpx

from . import __version__
from .errors import FetchError

FETCH_TIMEOUT = 30
MAX_RESPONSE_SIZE = 10 * 1024 * 1024
USER_AGENT = (
    f"mcp-feed-reader-crunchtools/{__version__} (+https://github.com/crunchtools/mcp-feed-reader)"
)

# Reddit throttles per exit IP and returns 429 for a few seconds at a time;
# gateways and CDNs return 5xx just as briefly. Both usually clear on a second
# look, and a crawl that gives up on the first one silently loses a day of
# entries -- a feed's history is not re-fetchable once it rolls off.
TRANSIENT_STATUSES = frozenset({429, 500, 502, 503, 504})
MAX_ATTEMPTS = 3
RETRY_BACKOFF_SECONDS = 2.0


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


async def _download(url: str, etag: str | None, last_modified: str | None) -> httpx.Response | None:
    """Download a feed URL, returning None on 304.

    A transient answer (connection error, rate limit, gateway 5xx) is retried
    up to MAX_ATTEMPTS times with exponential backoff. A definite one -- any
    other status -- is acted on immediately; retrying a 404 or a 401 only
    slows the crawl down.
    """
    headers: dict[str, str] = {"User-Agent": USER_AGENT}
    if etag:
        headers["If-None-Match"] = etag
    if last_modified:
        headers["If-Modified-Since"] = last_modified

    last_error = "no attempt made"
    last_exc: httpx.HTTPError | None = None
    for attempt in range(MAX_ATTEMPTS):
        if attempt:
            await asyncio.sleep(RETRY_BACKOFF_SECONDS * 2 ** (attempt - 1))

        try:
            async with httpx.AsyncClient(
                timeout=FETCH_TIMEOUT,
                follow_redirects=True,
                max_redirects=5,
            ) as client:
                response = await client.get(url, headers=headers)
        except httpx.HTTPError as exc:
            last_error, last_exc = str(exc) or type(exc).__name__, exc
            continue

        if response.status_code in TRANSIENT_STATUSES:
            last_error = f"HTTP {response.status_code}"
            continue
        if response.status_code == 304:
            return None
        if response.status_code != 200:
            raise FetchError(url, f"HTTP {response.status_code}")
        if len(response.content) > MAX_RESPONSE_SIZE:
            raise FetchError(url, "Response exceeds 10MB limit")
        return response

    # from last_exc keeps the underlying transport error in the traceback; a
    # run of rate limits has no such cause, and None says so honestly.
    raise FetchError(url, last_error) from last_exc


def _parse_entry(entry: Any) -> dict[str, Any]:
    """Extract fields from a feedparser entry."""
    entry_content = getattr(entry, "content", None)
    entry_summary = getattr(entry, "summary", None)
    content = entry_content[0].get("value", "") if entry_content else entry_summary or ""

    published: str | None = None
    for attr in ("published_parsed", "updated_parsed"):
        parsed_time = getattr(entry, attr, None)
        if parsed_time:
            with contextlib.suppress(TypeError, ValueError):
                dt = datetime(
                    parsed_time[0],
                    parsed_time[1],
                    parsed_time[2],
                    parsed_time[3],
                    parsed_time[4],
                    parsed_time[5],
                    tzinfo=timezone.utc,
                )
                published = dt.isoformat()
                break

    guid = entry.get("id") or entry.get("link") or entry.get("title", "")

    return {
        "guid": guid,
        "title": entry.get("title", ""),
        "url": entry.get("link", ""),
        "author": entry.get("author", ""),
        "content": content,
        "published": published,
    }


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
