"""Application factory: middleware, routers, error handlers and the SPA fallback."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import sessionmaker
from starlette.middleware.sessions import SessionMiddleware

from app import __version__
from app.api.v1.router import router as api_v1_router
from app.config import Settings, get_settings
from app.db import create_engine_from_settings
from app.errors import problem_responses, register_exception_handlers, use_problem_media_type
from app.logging import configure_logging
from app.middleware import (
    BodySizeLimitMiddleware,
    RequestIDMiddleware,
    SecurityHeadersMiddleware,
    TrustedHostMiddleware,
)
from app.security.csrf import OriginCheckMiddleware
from app.security.oauth import build_oauth

API_PREFIX = "/api/v1"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        yield
        app.state.engine.dispose()

    app = FastAPI(
        title="BrewNotes API",
        version=__version__,
        summary="Recipe design, brewing log, tasting notes and beer discovery.",
        openapi_url=f"{API_PREFIX}/openapi.json",
        docs_url=f"{API_PREFIX}/docs" if settings.is_development else None,
        redoc_url=None,
        responses=problem_responses(),
        lifespan=lifespan,
    )
    app.state.settings = settings
    engine = create_engine_from_settings(settings)
    app.state.engine = engine
    app.state.session_factory = sessionmaker(engine)
    app.state.oauth = build_oauth(settings)
    app.state.rate_limiters = {}

    register_exception_handlers(app)
    app.include_router(api_v1_router, prefix=API_PREFIX)
    _mount_frontend(app, settings)

    # add_middleware wraps outermost-last, so this order runs: request ID, security headers,
    # body limit, trusted host, CSRF origin check, OAuth state cookie, then the application.
    allowed_hosts = list(settings.allowed_hosts)
    if settings.app_env == "test":
        allowed_hosts.append("testserver")
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.secret_key,
        session_cookie=settings.oauth_cookie_name,
        max_age=settings.oauth_state_max_age_s,
        same_site="lax",
        https_only=settings.secure_cookies,
    )
    app.add_middleware(OriginCheckMiddleware, allowed_origin=settings.public_base_url)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)
    app.add_middleware(BodySizeLimitMiddleware, max_bytes=settings.max_body_bytes)
    app.add_middleware(SecurityHeadersMiddleware, settings=settings)
    app.add_middleware(RequestIDMiddleware)

    _install_openapi(app)
    return app


def _install_openapi(app: FastAPI) -> None:
    original = app.openapi

    def openapi_with_problem_media_type() -> dict[str, Any]:
        if app.openapi_schema is None:
            app.openapi_schema = use_problem_media_type(original())
        return app.openapi_schema

    app.openapi = openapi_with_problem_media_type  # type: ignore[method-assign]


def _mount_frontend(app: FastAPI, settings: Settings) -> None:
    """Serve the built frontend from one origin: hashed assets as immutable, index.html for
    every non-API path so deep links work, and a JSON 404 for unknown API paths."""
    static_dir = settings.static_dir
    if static_dir is None:
        return
    index_file = static_dir / "index.html"
    if not index_file.is_file():
        raise RuntimeError(f"STATIC_DIR is set but {index_file} does not exist")

    assets_dir = static_dir / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.api_route("/{full_path:path}", methods=["GET", "HEAD"], include_in_schema=False)
    def spa_fallback(full_path: str) -> FileResponse:
        if full_path == "api" or full_path.startswith("api/"):
            # Unknown API paths get a JSON 404, never index.html.
            raise HTTPException(HTTPStatus.NOT_FOUND, detail="No such API route.")
        candidate = (static_dir / full_path).resolve()
        if (
            full_path
            and candidate.is_file()
            and candidate.is_relative_to(static_dir.resolve())
            and candidate != index_file.resolve()
        ):
            return FileResponse(candidate)
        return FileResponse(index_file, headers={"Cache-Control": "no-cache"})
