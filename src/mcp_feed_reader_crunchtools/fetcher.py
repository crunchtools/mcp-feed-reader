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

# How much of a body to quote back in an error. Enough to recognise a WAF page,
# a parked-domain holder or a proxy error; short enough to stay readable.
BODY_SNIPPET_CHARS = 200
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
    downloaded = await _download(url, etag, last_modified)
    if downloaded is None:
        return None
    response, body = downloaded

    # The bytes rather than a decoded string: feedparser reads the XML
    # declaration and the charset for itself, and it is the only thing here that
    # knows what a feed claims its encoding is.
    parsed = feedparser.parse(body)

    # `version` is the format feedparser recognised -- `rss20`, `atom10` and so
    # on -- and it is empty for anything that is not a feed at all. It is the
    # only reliable signal here, because an HTML page comes back `bozo=False`
    # with zero entries, which is indistinguishable from a feed that happens to
    # be empty. A Cloudflare "Just a moment..." challenge is such a page, so
    # until this check existed a feed behind bot protection was recorded as a
    # feed with no entries and lost silently -- the RT #1596 failure, in the one
    # server that reaches arbitrary sites.
    if not parsed.version:
        raise FetchError(url, f"{_where(response)} is not a feed: {_body_snippet(body)}")
    if parsed.bozo and not parsed.entries:
        raise FetchError(
            url,
            f"{_where(response)} did not parse as a feed "
            f"({parsed.bozo_exception}): {_body_snippet(body)}",
        )

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


def _body_snippet(body: bytes) -> str:
    """A short, single-line excerpt of a response body, for an error message."""
    # Slice the bytes, then decode only that: a WAF page can be megabytes, and
    # decoding all of it to keep 200 characters copies it twice for nothing.
    prefix = body[: BODY_SNIPPET_CHARS * 4]
    collapsed = " ".join(prefix.decode("utf-8", errors="replace").split())
    if not collapsed:
        return "<empty body>"
    if len(collapsed) > BODY_SNIPPET_CHARS or len(body) > len(prefix):
        return collapsed[:BODY_SNIPPET_CHARS] + "..."
    return collapsed


def _where(response: httpx.Response) -> str:
    """Which request a response answered, for an error message.

    The requested URL rather than the feed URL that was asked for: redirects are
    followed here, so the two differ exactly when it matters -- a feed that now
    answers from a parked domain or a login page.
    """
    return (
        f"GET {response.request.url} (HTTP {response.status_code}, "
        f"{response.headers.get('content-type', 'no content-type')})"
    )


async def _read_capped(response: httpx.Response, url: str) -> bytes:
    """Read the body, aborting as soon as it passes MAX_RESPONSE_SIZE.

    The cap is enforced while reading. Checking `len(response.content)` after
    the fact is not a ceiling: by then the whole body is in memory, which is
    what the limit exists to prevent. `content-length` alone is not one either,
    because the header is optional and a chunked reply carries none.
    """
    declared = response.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > MAX_RESPONSE_SIZE:
        raise FetchError(
            url,
            f"{_where(response)} declared {declared} bytes, over the "
            f"{MAX_RESPONSE_SIZE} byte limit",
        )
    chunks: list[bytes] = []
    size = 0
    async for chunk in response.aiter_bytes():
        size += len(chunk)
        if size > MAX_RESPONSE_SIZE:
            raise FetchError(
                url, f"{_where(response)} sent over the {MAX_RESPONSE_SIZE} byte limit"
            )
        chunks.append(chunk)
    return b"".join(chunks)


async def _download(
    url: str, etag: str | None, last_modified: str | None
) -> tuple[httpx.Response, bytes] | None:
    """Download a feed URL, returning None on 304.

    A transient answer (connection error, rate limit, gateway 5xx) is retried
    with exponential backoff, for MAX_ATTEMPTS requests in all. A definite one
    -- any other status -- is acted on immediately; retrying a 404 or a 401
    only slows the crawl down.
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
                request = client.build_request("GET", url, headers=headers)
                response = await client.send(request, stream=True)
                try:
                    body = await _read_capped(response, url)
                finally:
                    await response.aclose()
        except httpx.HTTPError as exc:
            last_error, last_exc = str(exc) or type(exc).__name__, exc
            continue

        if response.status_code in TRANSIENT_STATUSES:
            last_error = _where(response)
            continue
        if response.status_code == 304:
            return None
        if response.status_code != 200:
            raise FetchError(url, f"{_where(response)} returned {_body_snippet(body)}")
        return response, body

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
