"""Error hierarchy for mcp-feed-reader-crunchtools."""

from __future__ import annotations


class FeedReaderError(Exception):
    """Base error for all feed reader operations."""


class FeedNotFoundError(FeedReaderError):
    """Raised when a feed ID does not exist."""

    def __init__(self, feed_id: int) -> None:
        super().__init__(f"Feed not found: {feed_id}")


class EntryNotFoundError(FeedReaderError):
    """Raised when an entry ID does not exist."""

    def __init__(self, entry_id: int) -> None:
        super().__init__(f"Entry not found: {entry_id}")


class CategoryNotFoundError(FeedReaderError):
    """Raised when a category ID does not exist."""

    def __init__(self, category_id: int) -> None:
        super().__init__(f"Category not found: {category_id}")


class DuplicateFeedError(FeedReaderError):
    """Raised when adding a feed URL that already exists."""

    def __init__(self, url: str) -> None:
        super().__init__(f"Feed already exists: {url}")


class DuplicateCategoryError(FeedReaderError):
    """Raised when creating a category name that already exists."""

    def __init__(self, name: str) -> None:
        super().__init__(f"Category already exists: {name}")


class FetchError(FeedReaderError):
    """Raised when fetching a feed URL fails."""

    def __init__(self, url: str, reason: str) -> None:
        super().__init__(f"Failed to fetch {url}: {reason}")
