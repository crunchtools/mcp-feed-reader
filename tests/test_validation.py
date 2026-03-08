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


class TestSearchParams:
    def test_valid(self) -> None:
        params = SearchParams(query="test")
        assert params.query == "test"

    def test_empty_query(self) -> None:
        with pytest.raises(ValidationError):
            SearchParams(query="")
