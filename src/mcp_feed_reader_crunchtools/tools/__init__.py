"""Tool implementations for mcp-feed-reader-crunchtools."""

from .categories import (
    create_category,
    delete_category,
    list_categories,
    rename_category,
)
from .entries import (
    list_entries,
    mark_read,
    mark_unread,
    read_entry,
    search_entries,
)
from .feeds import (
    add_feed,
    delete_feed,
    fetch_feeds,
    get_feed,
    list_feeds,
)
from .opml import (
    export_opml,
    get_stats,
    import_opml,
)

__all__ = [
    # feeds
    "add_feed",
    "list_feeds",
    "get_feed",
    "delete_feed",
    "fetch_feeds",
    # entries
    "list_entries",
    "read_entry",
    "mark_read",
    "mark_unread",
    "search_entries",
    # categories
    "list_categories",
    "create_category",
    "rename_category",
    "delete_category",
    # opml
    "import_opml",
    "export_opml",
    "get_stats",
]
