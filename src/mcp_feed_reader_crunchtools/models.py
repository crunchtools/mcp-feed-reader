"""Pydantic models for mcp-feed-reader-crunchtools."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any

from pydantic import BaseModel, BeforeValidator, Field, field_validator, model_validator

MAX_URL_LENGTH = 2048
MAX_NAME_LENGTH = 200
MAX_QUERY_LENGTH = 500
DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 500
MAX_SINCE_DAYS = 366


def unset_if_not_id(value: Any) -> Any:
    """Map a non-positive ID to None ("not given").

    SQLite row IDs start at 1. Tool-calling models that fill every optional
    parameter send ``feed_id: 0`` meaning "any", which used to fail as
    "Feed not found: 0" (RT #1505).
    """
    # bool is an int subclass: leave it for the strict field type to reject,
    # rather than reading False as ID 0.
    if isinstance(value, int) and not isinstance(value, bool) and value <= 0:
        return None
    return value


# Tool-signature ID types (constitution mcp-server 1.5.0). The schema publishes
# the valid domain, ``minimum: 1``, so a gateway can tell an out-of-domain
# value from a real one. An optional ID still maps a non-positive value to
# None BEFORE the constraint runs, so a client that sends ``0`` directly is
# served, not refused. A required ID keeps rejecting it.
RequiredId = Annotated[int, Field(ge=1)]
# The bound sits on the int branch, not the union: on the union, Pydantic
# publishes a bare ``ge`` that no JSON Schema reader understands.
OptionalId = Annotated[RequiredId | None, BeforeValidator(unset_if_not_id)]


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

    feed_id: int | None = Field(default=None, strict=True)
    category_id: int | None = Field(default=None, strict=True)
    unread_only: bool = True
    limit: int = Field(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE)
    offset: int = Field(default=0, ge=0)
    since_days: int | None = Field(default=None, ge=1, le=MAX_SINCE_DAYS)
    published_after: str | None = Field(default=None, max_length=MAX_NAME_LENGTH)
    published_before: str | None = Field(default=None, max_length=MAX_NAME_LENGTH)

    @field_validator("feed_id", "category_id", mode="before")
    @classmethod
    def _unset_non_ids(cls, v: Any) -> Any:
        return unset_if_not_id(v)

    @field_validator("published_after", "published_before", mode="before")
    @classmethod
    def _blank_bound_is_unset(cls, v: Any) -> Any:
        """``""`` means no bound, the same as omitting it (RT #1505)."""
        if isinstance(v, str) and not v.strip():
            return None
        return v

    @field_validator("published_after", "published_before")
    @classmethod
    def _normalize_bounds(cls, v: str | None) -> str | None:
        """Normalize an ISO-8601 date/datetime bound to 'YYYY-MM-DD HH:MM:SS' UTC.

        Accepts date-only, offset-bearing, and 'Z' inputs; tz-aware values are
        converted to UTC, naive values are assumed UTC. Raises on unparseable input.
        """
        if v is None:
            return None
        candidate = v.strip().replace("Z", "+00:00").replace("z", "+00:00")
        try:
            parsed = datetime.fromisoformat(candidate)
        except ValueError as exc:
            msg = f"Invalid timestamp {v!r}: expected ISO-8601 date or datetime"
            raise ValueError(msg) from exc
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(timezone.utc)
        return parsed.strftime("%Y-%m-%d %H:%M:%S")

    @model_validator(mode="after")
    def _check_window(self) -> EntryListParams:
        if self.since_days is not None and (
            self.published_after is not None or self.published_before is not None
        ):
            msg = "since_days is mutually exclusive with published_after/published_before"
            raise ValueError(msg)
        return self


class SearchParams(BaseModel, extra="forbid"):
    """Parameters for searching entries."""

    query: str = Field(..., min_length=1, max_length=MAX_QUERY_LENGTH)
    limit: int = Field(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE)
