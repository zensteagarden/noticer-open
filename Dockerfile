# Noticer commercial MCP 0.3.2-dev.20261016 — stdio server for the Docker MCP Catalog.
# Public client only (mcp-commercial/0.3.2-dev.20261016, Apache-2.0). No private engine code.
# Pricing: 5 free checks, then USD 1 per eligible check by card or Link; INCONCLUSIVE is free.
FROM docker.io/library/python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1
COPY --from=docker.io/astral/uv:0.12.24@sha256:3af4716e991d6956a41e573eab705d0ee08500cd829ed30293eb8472f372c65a /uv /usr/local/bin/uv
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_COMPILE_BYTECODE=0 UV_LINK_MODE=copy
WORKDIR /app
COPY mcp-commercial/0.3.2-dev.20261016/pyproject.toml mcp-commercial/0.3.2-dev.20261016/uv.lock /app/
RUN uv sync --frozen --no-dev --no-install-project
COPY mcp-commercial/0.3.2-dev.20261016/ /app/
RUN rm -rf /app/tests /app/__pycache__ \
 && useradd --create-home --uid 10001 noticer \
 && mkdir -p /data && chown noticer:noticer /data
USER noticer
# Local setup state (private buyer key file, saved orders) lives here; mount a volume to keep it.
ENV HOME=/home/noticer XDG_STATE_HOME=/data
VOLUME ["/data"]
ENTRYPOINT ["/app/.venv/bin/python", "/app/sales_mcp.py"]
