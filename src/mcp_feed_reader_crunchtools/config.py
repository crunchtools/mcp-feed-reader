"""Configuration for mcp-feed-reader-crunchtools."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pydantic import SecretStr

_config: Config | None = None


class Config:
    """Feed reader configuration from environment variables.

    No API credentials required. The _api_token field is typed as
    SecretStr | None for constitution compliance and future extensibility.
    """

    _api_token: SecretStr | None = None

    def __init__(self) -> None:
        default_db = str(
            Path.home() / ".local" / "share" / "mcp-feed-reader" / "feeds.db"
        )
        self.db_path: str = os.environ.get("FEED_READER_DB", default_db)

    def ensure_db_dir(self) -> None:
        """Create the database directory if it does not exist."""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)


def get_config() -> Config:
    """Get or create the singleton configuration."""
    global _config
    if _config is None:
        _config = Config()
    return _config
