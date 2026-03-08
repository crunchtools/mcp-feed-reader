"""Pydantic models for mcp-feed-reader-crunchtools."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

MAX_URL_LENGTH = 2048
MAX_NAME_LENGTH = 200
MAX_QUERY_LENGTH = 500
DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 500


class FeedInput(BaseModel, extra="forbid"):
    """Input for adding a new feed."""

    url: str = Field(..., min_length=1, max_length=MAX_URL_LENGTH)
    category: str | None = Field(default=None, max_length=MAX_NAME_LENGTH)

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        if not v.startswith(("http://", "https://")):
            msg = "URL must start with http:// or https://"
            raise ValueError(msg)
        return v


class CategoryInput(BaseModel, extra="forbid"):
    """Input for creating or renaming a category."""

    name: str = Field(..., min_length=1, max_length=MAX_NAME_LENGTH)


class EntryListParams(BaseModel, extra="forbid"):
    """Parameters for listing entries."""

    feed_id: int | None = None
    category_id: int | None = None
    unread_only: bool = True
    limit: int = Field(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE)
    offset: int = Field(default=0, ge=0)


class SearchParams(BaseModel, extra="forbid"):
    """Parameters for searching entries."""

    query: str = Field(..., min_length=1, max_length=MAX_QUERY_LENGTH)
    limit: int = Field(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE)
