"""Pydantic model validation tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from mcp_feed_reader_crunchtools.models import (
    CategoryInput,
    EntryListParams,
    FeedInput,
    SearchParams,
)


class TestFeedInput:
    def test_valid_url(self) -> None:
        feed = FeedInput(url="https://example.com/feed.xml")
        assert feed.url == "https://example.com/feed.xml"

    def test_valid_with_category(self) -> None:
        feed = FeedInput(url="https://example.com/feed.xml", category="Tech")
        assert feed.category == "Tech"

    def test_invalid_url_scheme(self) -> None:
        with pytest.raises(ValidationError, match="http://"):
            FeedInput(url="ftp://example.com/feed.xml")

    def test_empty_url(self) -> None:
        with pytest.raises(ValidationError):
            FeedInput(url="")

    def test_extra_fields_rejected(self) -> None:
        with pytest.raises(ValidationError):
            FeedInput.model_validate({"url": "https://example.com/feed.xml", "extra": "bad"})


class TestCategoryInput:
    def test_valid(self) -> None:
        cat = CategoryInput(name="Tech")
        assert cat.name == "Tech"

    def test_empty_name(self) -> None:
        with pytest.raises(ValidationError):
            CategoryInput(name="")

    def test_long_name(self) -> None:
        with pytest.raises(ValidationError):
            CategoryInput(name="x" * 201)


class TestEntryListParams:
    def test_defaults(self) -> None:
        params = EntryListParams()
        assert params.unread_only is True
        assert params.limit == 50
        assert params.offset == 0

    def test_limit_too_high(self) -> None:
        with pytest.raises(ValidationError):
            EntryListParams(limit=501)

    def test_negative_offset(self) -> None:
        with pytest.raises(ValidationError):
            EntryListParams(offset=-1)

    def test_since_days_defaults_none(self) -> None:
        params = EntryListParams()
        assert params.since_days is None
        assert params.published_after is None
        assert params.published_before is None

    def test_since_days_out_of_range(self) -> None:
        with pytest.raises(ValidationError):
            EntryListParams(since_days=0)
        with pytest.raises(ValidationError):
            EntryListParams(since_days=367)

    def test_published_after_normalized_utc(self) -> None:
        """Offset-bearing input is converted to a canonical UTC string."""
        params = EntryListParams(published_after="2026-08-23T05:00:00+02:00")
        assert params.published_after == "2026-08-23 03:00:00"

    def test_published_bounds_date_only(self) -> None:
        params = EntryListParams(published_after="2026-08-23")
        assert params.published_after == "2026-08-23 00:00:00"

    def test_published_z_suffix(self) -> None:
        params = EntryListParams(published_before="2026-08-30T12:00:00Z")
        assert params.published_before == "2026-08-30 12:00:00"

    def test_invalid_timestamp(self) -> None:
        with pytest.raises(ValidationError, match="Invalid timestamp"):
            EntryListParams(published_after="not-a-date")

    def test_since_days_mutually_exclusive(self) -> None:
        with pytest.raises(ValidationError, match="mutually exclusive"):
            EntryListParams(since_days=7, published_after="2026-08-23")
        with pytest.raises(ValidationError, match="mutually exclusive"):
            EntryListParams(since_days=7, published_before="2026-08-30")


class TestSearchParams:
    def test_valid(self) -> None:
        params = SearchParams(query="test")
        assert params.query == "test"

    def test_empty_query(self) -> None:
        with pytest.raises(ValidationError):
            SearchParams(query="")
