"""mcp-feed-reader-crunchtools: RSS/Atom feed reader MCP server."""

from __future__ import annotations

import argparse
import asyncio
import sys

__version__ = "0.1.2"


def main() -> None:
    """Entry point for mcp-feed-reader-crunchtools."""
    parser = argparse.ArgumentParser(
        prog="mcp-feed-reader-crunchtools",
        description="RSS/Atom feed reader MCP server with SQLite backend",
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse", "streamable-http"],
        default="stdio",
        help="MCP transport (default: stdio)",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="HTTP host (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="HTTP port (default: 8000)",
    )
    parser.add_argument(
        "--fetch",
        action="store_true",
        help="Fetch all feeds and exit (for systemd timer)",
    )

    args = parser.parse_args()

    if args.fetch:
        _run_fetch()
        return

    from .database import get_db
    from .server import mcp

    get_db()

    match args.transport:
        case "stdio":
            mcp.run(transport="stdio")
        case "sse":
            mcp.run(transport="sse", host=args.host, port=args.port)
        case _:
            mcp.run(transport="streamable-http", host=args.host, port=args.port)


def _run_fetch() -> None:
    """Fetch all feeds (CLI mode for systemd timer)."""
    from .database import get_db
    from .tools.feeds import fetch_feeds

    get_db()
    fetch_summary = asyncio.run(fetch_feeds())
    print(fetch_summary)
    sys.exit(0)
