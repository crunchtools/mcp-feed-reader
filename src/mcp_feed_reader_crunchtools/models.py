"""Pydantic models for mcp-feed-reader-crunchtools."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class FeedInput(BaseModel, extra="forbid"):
    """Input for adding a new feed."""

    url: str = Field(..., min_length=1, max_length=2048)
    category: str | None = Field(default=None, max_length=200)

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        if not v.startswith(("http://", "https://")):
            msg = "URL must start with http:// or https://"
            raise ValueError(msg)
        return v


class CategoryInput(BaseModel, extra="forbid"):
    """Input for creating or renaming a category."""

    name: str = Field(..., min_length=1, max_length=200)


class EntryListParams(BaseModel, extra="forbid"):
    """Parameters for listing entries."""

    feed_id: int | None = None
    category_id: int | None = None
    unread_only: bool = True
    limit: int = Field(default=50, ge=1, le=500)
    offset: int = Field(default=0, ge=0)


class SearchParams(BaseModel, extra="forbid"):
    """Parameters for searching entries."""

    query: str = Field(..., min_length=1, max_length=500)
    limit: int = Field(default=50, ge=1, le=500)
