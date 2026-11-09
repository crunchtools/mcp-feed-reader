"""Fetcher tests: retry policy against a mocked transport, no real network."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import httpx
import pytest

from mcp_feed_reader_crunchtools import fetcher
from mcp_feed_reader_crunchtools.errors import FetchError

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable

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
        """A declared length over the cap is rejected before the body is read."""
        oversize = "x" * (fetcher.MAX_RESPONSE_SIZE + 1)
        transport(httpx.Response(200, text=oversize))
        with pytest.raises(FetchError) as caught:
            await fetcher.fetch_feed(URL)

        assert str(caught.value) == (
            "Failed to fetch https://example.com/feed.xml: "
            "GET https://example.com/feed.xml (HTTP 200, text/plain; charset=utf-8) "
            f"declared {fetcher.MAX_RESPONSE_SIZE + 1} bytes, over the "
            f"{fetcher.MAX_RESPONSE_SIZE} byte limit"
        )

    async def test_chunked_oversize_response_is_refused(
        self, transport: Callable[..., list[str]], backoff: list[float]
    ) -> None:
        """No content-length at all: the case a header check waves through.

        The old code read `response.content` in full and only then compared its
        length, so the limit it claimed to enforce had already been exceeded in
        memory by the time it looked.
        """

        async def chunks() -> AsyncIterator[bytes]:
            for _ in range(11):
                yield b"x" * (1024 * 1024)

        answer = httpx.Response(
            200, headers={"content-type": "application/rss+xml"}, content=chunks()
        )
        assert "content-length" not in answer.headers
        transport(answer)

        with pytest.raises(FetchError) as caught:
            await fetcher.fetch_feed(URL)

        assert str(caught.value) == (
            "Failed to fetch https://example.com/feed.xml: "
            "GET https://example.com/feed.xml (HTTP 200, application/rss+xml) "
            f"sent over the {fetcher.MAX_RESPONSE_SIZE} byte limit"
        )

    async def test_a_definite_failure_says_what_came_back(
        self, transport: Callable[..., list[str]], backoff: list[float]
    ) -> None:
        """`HTTP 404` alone cannot tell a dead feed from a WAF page (RT #1596)."""
        transport(
            httpx.Response(
                403, headers={"content-type": "text/html"}, text="<title>Just a moment...</title>"
            )
        )
        with pytest.raises(FetchError) as caught:
            await fetcher.fetch_feed(URL)

        assert str(caught.value) == (
            "Failed to fetch https://example.com/feed.xml: "
            "GET https://example.com/feed.xml (HTTP 403, text/html) "
            "returned <title>Just a moment...</title>"
        )

    async def test_a_challenge_page_is_not_an_empty_feed(
        self, transport: Callable[..., list[str]], backoff: list[float]
    ) -> None:
        """The RT #1596 shape, and this repo had it silently.

        feedparser answers an HTML page with `bozo=False` and zero entries,
        exactly like a feed that happens to be empty, so a feed behind bot
        protection was recorded as having no entries and lost without a word.
        """
        transport(
            httpx.Response(
                200,
                headers={"content-type": "text/html"},
                text="<!DOCTYPE html><title>Just a moment...</title>",
            )
        )
        with pytest.raises(FetchError) as caught:
            await fetcher.fetch_feed(URL)

        assert str(caught.value) == (
            "Failed to fetch https://example.com/feed.xml: "
            "GET https://example.com/feed.xml (HTTP 200, text/html) is not a feed: "
            "<!DOCTYPE html><title>Just a moment...</title>"
        )

    async def test_a_valid_but_empty_feed_is_still_a_feed(
        self, transport: Callable[..., list[str]], backoff: list[float]
    ) -> None:
        """The other side of that guard: zero entries is not an error by itself."""
        empty = (
            '<?xml version="1.0"?><rss version="2.0"><channel>'
            "<title>Quiet Feed</title></channel></rss>"
        )
        transport(httpx.Response(200, headers={"content-type": "application/rss+xml"}, text=empty))

        result = await fetcher.fetch_feed(URL)

        assert result is not None
        assert result.title == "Quiet Feed"
        assert result.entries == []

    async def test_a_body_that_is_broken_xml_says_what_it_was(
        self, transport: Callable[..., list[str]], backoff: list[float]
    ) -> None:
        transport(
            httpx.Response(200, headers={"content-type": "application/json"}, text='{"error": 1}')
        )
        with pytest.raises(FetchError) as caught:
            await fetcher.fetch_feed(URL)

        message = str(caught.value)
        assert "(HTTP 200, application/json)" in message
        assert '{"error": 1}' in message


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

    async def test_an_oversize_transient_answer_is_still_retried(
        self, transport: Callable[..., list[str]], backoff: list[float]
    ) -> None:
        """A 503 page too big to read is still a 503, not a permanent failure.

        Reading the body before looking at the status would raise `FetchError`
        out of the retry loop, which `except httpx.HTTPError` does not catch.
        """
        huge = "x" * (fetcher.MAX_RESPONSE_SIZE + 1)
        log = transport(
            httpx.Response(503, headers={"content-type": "text/html"}, text=huge),
            httpx.Response(200, headers={"content-type": "application/rss+xml"}, text=FEED_XML),
        )

        result = await fetcher.fetch_feed(URL)

        assert result is not None
        assert result.title == "Example Feed"
        assert len(log) == 2
