"""The cron job that removes expired sessions."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session
from typer.testing import CliRunner

from app.cli import cli
from app.config import Settings, get_settings
from app.models import User, UserSession


def test_cleanup_sessions_deletes_expired_and_idle_sessions(
    engine: Engine, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    now = datetime.now(UTC)
    with Session(engine) as db, db.begin():
        user = User(display_name="Cron Test")
        db.add(user)
        db.flush()
        user_id = user.id
        db.add_all(
            [
                UserSession(  # past absolute lifetime
                    user_id=user_id,
                    token_hash="a" * 64,
                    created_at=now - timedelta(days=40),
                    last_seen_at=now - timedelta(hours=1),
                    expires_at=now - timedelta(seconds=1),
                ),
                UserSession(  # idle for longer than allowed
                    user_id=user_id,
                    token_hash="b" * 64,
                    created_at=now - timedelta(days=20),
                    last_seen_at=now - timedelta(days=settings.session_idle_days, hours=1),
                    expires_at=now + timedelta(days=10),
                ),
                UserSession(  # live
                    user_id=user_id,
                    token_hash="c" * 64,
                    created_at=now,
                    last_seen_at=now,
                    expires_at=now + timedelta(days=30),
                ),
            ]
        )
    try:
        for name, value in {
            "APP_ENV": "test",
            "DATABASE_URL": settings.database_url,
            "SECRET_KEY": settings.secret_key,
            "PUBLIC_BASE_URL": settings.public_base_url,
        }.items():
            monkeypatch.setenv(name, value)
        get_settings.cache_clear()
        result = CliRunner().invoke(cli, ["cleanup-sessions"])
        assert result.exit_code == 0, result.output
        assert "deleted 2 expired sessions" in result.output

        with Session(engine) as db:
            remaining = db.execute(
                select(func.count()).select_from(UserSession).where(UserSession.user_id == user_id)
            ).scalar_one()
            assert remaining == 1
            hashes = db.scalars(
                select(UserSession.token_hash).where(UserSession.user_id == user_id)
            ).all()
            assert hashes == ["c" * 64]
    finally:
        get_settings.cache_clear()
        with Session(engine) as db, db.begin():
            victim = db.get(User, uuid.UUID(str(user_id)))
            if victim is not None:
                db.delete(victim)
