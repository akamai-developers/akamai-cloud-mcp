# Container image for the streamable-HTTP transport.
#
# Build:  docker build -t akamai-cloud-mcp .
# Run:    docker run -p 8080:8080 \
#           -e LINODE_TOKEN=<your-linode-token> \
#           -e AKAMAI_MCP_HTTP_AUTH_TOKEN=<bearer-token> \
#           akamai-cloud-mcp
#
# The HTTP transport uses ONE shared server-side LINODE_TOKEN. Put it behind auth
# (AKAMAI_MCP_HTTP_AUTH_TOKEN) and TLS. See the README HTTP deploy section.

FROM python:3.12-slim

# Install uv for a fast, reproducible install.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Install dependencies first for better layer caching.
COPY pyproject.toml uv.lock README.md ./
COPY src ./src

RUN uv sync --frozen --no-dev

EXPOSE 8080

ENV AKAMAI_MCP_HOST=0.0.0.0 \
    AKAMAI_MCP_PORT=8080 \
    AKAMAI_MCP_PATH=/mcp

ENTRYPOINT ["uv", "run", "akamai-cloud-mcp"]
CMD ["--transport", "streamable-http", "--host", "0.0.0.0", "--port", "8080", "--path", "/mcp"]
