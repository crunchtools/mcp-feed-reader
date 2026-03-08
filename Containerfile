# MCP Feed Reader CrunchTools Container
# Built on Hummingbird Python image (Red Hat UBI-based) for enterprise security
#
# Build:
#   podman build -t quay.io/crunchtools/mcp-feed-reader .
#
# Run:
#   podman run -v feedreader-data:/data quay.io/crunchtools/mcp-feed-reader
#
# With Claude Code:
#   claude mcp add mcp-feed-reader-crunchtools \
#     -- podman run -i --rm -v feedreader-data:/data quay.io/crunchtools/mcp-feed-reader

FROM quay.io/hummingbird/python:latest

LABEL name="mcp-feed-reader-crunchtools" \
      version="0.1.0" \
      summary="Secure MCP server for RSS/Atom feed reading" \
      description="A self-contained RSS/Atom feed reader MCP server with SQLite backend" \
      maintainer="crunchtools.com" \
      url="https://github.com/crunchtools/mcp-feed-reader" \
      io.k8s.display-name="MCP Feed Reader CrunchTools" \
      io.openshift.tags="mcp,rss,atom,feed-reader" \
      org.opencontainers.image.source="https://github.com/crunchtools/mcp-feed-reader" \
      org.opencontainers.image.description="Secure MCP server for RSS/Atom feed reading" \
      org.opencontainers.image.licenses="AGPL-3.0-or-later"

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src/ ./src/

RUN pip install --no-cache-dir .

RUN python -c "from mcp_feed_reader_crunchtools import main; print('Installation verified')"

ENV FEED_READER_DB=/data/feeds.db

RUN mkdir -p /data
VOLUME ["/data"]

EXPOSE 8018
ENTRYPOINT ["python", "-m", "mcp_feed_reader_crunchtools"]
