# MCP Feed Reader CrunchTools Container
# Built on Hummingbird Python image (Red Hat hardened, distroless)
#
# Build:
#   podman build -t quay.io/crunchtools/mcp-feed-reader .
#
# Run:
#   podman run -v feedreader-data:/data quay.io/crunchtools/mcp-feed-reader

# Stage 0: the locked dependency set (RT#1564). Dependencies come from
# uv.lock, not a fresh resolve: pyproject.toml floor-pins every dependency
# with no upper bound, so `pip install .` alone builds against whatever was
# released that morning rather than the set CI actually tested. uv is pinned
# so a cold runner installs with the same uv a warm one cached.
FROM quay.io/hummingbird/python:3.14-builder AS lock
USER 0
RUN pip install --no-cache-dir uv==0.13.7
WORKDIR /lock
COPY pyproject.toml uv.lock ./
RUN uv export --frozen --no-dev --no-emit-project \
      --format requirements-txt -o /requirements.txt

# Stage 1: Install dependencies (builder has /bin/sh)
FROM quay.io/hummingbird/python:3.14-builder AS pip-builder

USER 0
WORKDIR /app

RUN pip install --no-cache-dir uv==0.13.7
COPY --from=lock /requirements.txt /tmp/requirements.txt
RUN uv pip install --no-cache --prefix=/usr --no-deps -r /tmp/requirements.txt

COPY pyproject.toml README.md ./
COPY src/ ./src/

RUN uv pip install --no-cache --prefix=/usr --no-deps .

# Stage 2: Distroless runtime
FROM quay.io/hummingbird/python:3.14

LABEL name="mcp-feed-reader-crunchtools" \
      version="0.6.2" \
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
