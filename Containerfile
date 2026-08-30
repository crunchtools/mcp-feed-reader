# MCP Feed Reader CrunchTools Container
# Built on Hummingbird Python image (Red Hat hardened, distroless)
#
# Build:
#   podman build -t quay.io/crunchtools/mcp-feed-reader .
#
# Run:
#   podman run -v feedreader-data:/data quay.io/crunchtools/mcp-feed-reader

# Stage 1: Install dependencies (builder has /bin/sh)
FROM quay.io/hummingbird/python:latest-builder AS pip-builder

USER 0
WORKDIR /app

COPY pyproject.toml README.md ./
COPY src/ ./src/

RUN pip install --no-cache-dir --prefix=/usr .

# Stage 2: Distroless runtime
FROM quay.io/hummingbird/python:latest

LABEL name="mcp-feed-reader-crunchtools" \
      version="0.2.1" \
      summary="Secure MCP server for RSS/Atom feed reading" \
      description="A self-contained RSS/Atom feed reader MCP server with SQLite backend" \
      maintainer="crunchtools.com" \
      url="https://github.com/crunchtools/mcp-feed-reader" \
      io.k8s.display-name="MCP Feed Reader CrunchTools" \
      io.openshift.tags="mcp,rss,atom,feed-reader" \
      org.opencontainers.image.source="https://github.com/crunchtools/mcp-feed-reader" \
      org.opencontainers.image.description="Secure MCP server for RSS/Atom feed reading" \
      org.opencontainers.image.licenses="AGPL-3.0-or-later"

COPY --from=pip-builder /usr/lib/python3.14/site-packages/ /usr/lib/python3.14/site-packages/
COPY --from=pip-builder /usr/lib64/python3.14/site-packages/ /usr/lib64/python3.14/site-packages/

ENV FEED_READER_DB=/data/feeds.db

EXPOSE 8018
ENTRYPOINT ["python", "-m", "mcp_feed_reader_crunchtools"]
