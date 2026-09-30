"""Fetcher tests: retry policy against a mocked transport, no real network."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import httpx
import pytest

from mcp_feed_reader_crunchtools import fetcher
from mcp_feed_reader_crunchtools.errors import FetchError

if TYPE_CHECKING:
    from collections.abc import Callable

FEED_XML = """<?xml version="1.0"?>
<rss version="2.0"><channel>
  <title>Example Feed</title>
  <link>https://example.com/</link>
  <item>
    <title>First post</title>
    <link>https://example.com/1</link>
    <pubDate>Mon, 29 Sep 2026 12:00:00 GMT</pubDate>
  </item>
</channel></rss>
"""

URL = "https://example.com/feed.xml"


def _install(
    monkeypatch: pytest.MonkeyPatch, handler: Callable[[httpx.Request], httpx.Response]
) -> None:
    """Make the fetcher's clients speak to ``handler`` instead of the network."""
    real_client = httpx.AsyncClient

    def make_client(**kwargs: Any) -> httpx.AsyncClient:
        return real_client(transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(fetcher.httpx, "AsyncClient", make_client)


@pytest.fixture
def transport(monkeypatch: pytest.MonkeyPatch) -> Callable[..., list[str]]:
    """Point the fetcher at a scripted transport; returns the request log."""

    def install(*answers: httpx.Response | Exception) -> list[str]:
        """Serve ``answers`` in order; the last one repeats so a retry loop never runs dry."""
        log: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            answer = answers[min(len(log), len(answers) - 1)]
            log.append(str(request.url))
            if isinstance(answer, Exception):
                raise answer
            return answer

        _install(monkeypatch, handler)
        return log

    return install


@pytest.fixture
def backoff(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """Record backoff delays instead of waiting them out."""
    delays: list[float] = []

    async def _sleep(seconds: float) -> None:
        delays.append(seconds)

    monkeypatch.setattr(fetcher.asyncio, "sleep", _sleep)
    return delays


def _ok() -> httpx.Response:
    return httpx.Response(200, text=FEED_XML)


class TestRetry:
    async def test_success_on_first_attempt(
        self, transport: Callable[..., list[str]], backoff: list[float]
    ) -> None:
        log = transport(_ok())
        result = await fetcher.fetch_feed(URL)
        assert result is not None
        assert result.title == "Example Feed"
        assert len(log) == 1
        assert backoff == []

    @pytest.mark.parametrize("status", [429, 500, 502, 503, 504])
    async def test_transient_status_is_retried(
        self, transport: Callable[..., list[str]], backoff: list[float], status: int
    ) -> None:
        log = transport(httpx.Response(status), _ok())
        result = await fetcher.fetch_feed(URL)
        assert result is not None
        assert len(log) == 2

    async def test_connection_error_is_retried(
        self, transport: Callable[..., list[str]], backoff: list[float]
    ) -> None:
        log = transport(httpx.ConnectError("Server disconnected"), _ok())
        result = await fetcher.fetch_feed(URL)
        assert result is not None
        assert len(log) == 2

    async def test_gives_up_after_max_attempts(
        self, transport: Callable[..., list[str]], backoff: list[float]
    ) -> None:
        log = transport(httpx.Response(429))
        with pytest.raises(FetchError, match="HTTP 429"):
            await fetcher.fetch_feed(URL)
        assert len(log) == fetcher.MAX_ATTEMPTS

    async def test_backoff_doubles_between_attempts(
        self, transport: Callable[..., list[str]], backoff: list[float]
    ) -> None:
        transport(httpx.Response(503))
        with pytest.raises(FetchError):
            await fetcher.fetch_feed(URL)
        assert backoff == [
            fetcher.RETRY_BACKOFF_SECONDS,
            fetcher.RETRY_BACKOFF_SECONDS * 2,
        ]

    @pytest.mark.parametrize("status", [401, 403, 404, 410, 523])
    async def test_definite_error_is_not_retried(
        self, transport: Callable[..., list[str]], backoff: list[float], status: int
    ) -> None:
        log = transport(httpx.Response(status))
        with pytest.raises(FetchError, match=f"HTTP {status}"):
            await fetcher.fetch_feed(URL)
        assert len(log) == 1

    async def test_not_modified_is_not_retried(
        self, transport: Callable[..., list[str]], backoff: list[float]
    ) -> None:
        log = transport(httpx.Response(304))
        assert await fetcher.fetch_feed(URL, etag='"abc"') is None
        assert len(log) == 1

    async def test_oversize_response_is_refused(
        self, transport: Callable[..., list[str]], backoff: list[float]
    ) -> None:
        oversize = "x" * (fetcher.MAX_RESPONSE_SIZE + 1)
        transport(httpx.Response(200, text=oversize))
        with pytest.raises(FetchError, match="10MB"):
            await fetcher.fetch_feed(URL)


class TestConditionalHeaders:
    async def test_etag_and_last_modified_are_sent(
        self, monkeypatch: pytest.MonkeyPatch, backoff: list[float]
    ) -> None:
        seen: list[httpx.Headers] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(request.headers)
            return _ok()

        _install(monkeypatch, handler)
        await fetcher.fetch_feed(URL, etag='"abc"', last_modified="Mon, 29 Sep 2026 12:00:00 GMT")

        assert seen[0]["If-None-Match"] == '"abc"'
        assert seen[0]["If-Modified-Since"] == "Mon, 29 Sep 2026 12:00:00 GMT"
        assert seen[0]["User-Agent"] == fetcher.USER_AGENT
