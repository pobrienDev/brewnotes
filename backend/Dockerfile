# syntax=docker/dockerfile:1
# Build from the repository root:  docker build -f backend/Dockerfile -t brewnotes .
# One image serves the API and the built frontend from one origin.

# ---- Frontend build -------------------------------------------------------------------
FROM node:22-slim AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ---- Backend dependencies -------------------------------------------------------------
FROM python:3.13-slim AS backend
COPY --from=ghcr.io/astral-sh/uv:0.12.23 /uv /uvx /bin/
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv
# Dependencies first so they cache independently of application code.
COPY backend/pyproject.toml backend/uv.lock backend/README.md ./
RUN uv sync --locked --no-dev --no-install-project
COPY backend/ ./
RUN uv sync --locked --no-dev

# ---- Runtime --------------------------------------------------------------------------
FROM python:3.13-slim AS runtime
RUN groupadd --system app \
    && useradd --system --gid app --home-dir /app --shell /usr/sbin/nologin app
WORKDIR /app
ENV PATH=/app/.venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    APP_ENV=production \
    STATIC_DIR=/app/static
COPY --from=backend --chown=app:app /app /app
COPY --from=frontend --chown=app:app /build/dist /app/static
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s \
    CMD ["python", "-c", "import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health/live', timeout=2).status == 200 else 1)"]
# Migrations are a release step (`alembic upgrade head`), run before this version takes traffic.
CMD ["sh", "-c", "exec uvicorn app.asgi:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips \"${FORWARDED_ALLOW_IPS:-127.0.0.1}\""]
