from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Any, cast

from sqlalchemy import CursorResult, delete, or_, select
from sqlalchemy.orm import Session, joinedload

from app.models import UserSession


def create(
    db: Session, *, user_id: uuid.UUID, token_hash: str, now: datetime, lifetime: timedelta
) -> UserSession:
    session = UserSession(
        user_id=user_id,
        token_hash=token_hash,
        created_at=now,
        last_seen_at=now,
        expires_at=now + lifetime,
    )
    db.add(session)
    db.flush()
    return session


def get_active(
    db: Session, *, token_hash: str, now: datetime, idle: timedelta
) -> UserSession | None:
    """The session for this token if it is within both its idle and absolute limits."""
    return db.scalars(
        select(UserSession)
        .where(
            UserSession.token_hash == token_hash,
            UserSession.expires_at > now,
            UserSession.last_seen_at > now - idle,
        )
        .options(joinedload(UserSession.user))
    ).one_or_none()


def list_for_user(db: Session, user_id: uuid.UUID) -> list[UserSession]:
    return list(
        db.scalars(
            select(UserSession)
            .where(UserSession.user_id == user_id)
            .order_by(UserSession.created_at)
        )
    )


def delete_one(db: Session, session: UserSession) -> None:
    db.delete(session)
    db.flush()


def delete_all_for_user(db: Session, user_id: uuid.UUID) -> int:
    result = cast(
        "CursorResult[Any]", db.execute(delete(UserSession).where(UserSession.user_id == user_id))
    )
    return int(result.rowcount)


def delete_expired(db: Session, *, now: datetime, idle: timedelta) -> int:
    result = cast(
        "CursorResult[Any]",
        db.execute(
            delete(UserSession).where(
                or_(UserSession.expires_at <= now, UserSession.last_seen_at <= now - idle)
            )
        ),
    )
    return int(result.rowcount)
