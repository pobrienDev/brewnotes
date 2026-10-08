"""Server-side sessions: an opaque token in a cookie, only its SHA-256 stored in Postgres."""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from http import HTTPStatus

from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.config import Settings
from app.db import get_db
from app.models import User, UserSession
from app.repositories import session_repo

TOKEN_BYTES = 32


def generate_token() -> str:
    return secrets.token_urlsafe(TOKEN_BYTES)


def hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode()).hexdigest()


def set_session_cookie(response: Response, settings: Settings, raw_token: str) -> None:
    response.set_cookie(
        key=settings.session_cookie_name,
        value=raw_token,
        max_age=settings.session_absolute_days * 86400,
        path="/",
        secure=settings.secure_cookies,
        httponly=True,
        # Lax, not Strict, so a user arriving from a link is still recognised.
        samesite="lax",
    )


def clear_session_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        key=settings.session_cookie_name,
        path="/",
        secure=settings.secure_cookies,
        httponly=True,
        samesite="lax",
    )


def _settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def current_session(request: Request, db: Session = Depends(get_db)) -> UserSession | None:
    """The caller's live session, or None. Bumps last_seen_at at most once per hour."""
    settings = _settings(request)
    raw_token = request.cookies.get(settings.session_cookie_name)
    if not raw_token or len(raw_token) > 128:
        return None
    now = datetime.now(UTC)
    session = session_repo.get_active(
        db,
        token_hash=hash_token(raw_token),
        now=now,
        idle=timedelta(days=settings.session_idle_days),
    )
    if session is None:
        return None
    if now - session.last_seen_at >= timedelta(seconds=settings.session_touch_interval_s):
        session.last_seen_at = now
    request.state.session = session
    return session


def optional_user(session: UserSession | None = Depends(current_session)) -> User | None:
    return session.user if session is not None else None


def current_user(session: UserSession | None = Depends(current_session)) -> User:
    if session is None:
        raise HTTPException(HTTPStatus.UNAUTHORIZED, detail="Sign in required.")
    return session.user
