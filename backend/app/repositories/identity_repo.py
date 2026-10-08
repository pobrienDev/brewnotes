from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.models import OAuthIdentity


def get_by_subject(db: Session, provider: str, subject: str) -> OAuthIdentity | None:
    return db.scalars(
        select(OAuthIdentity)
        .where(OAuthIdentity.provider == provider, OAuthIdentity.provider_subject == subject)
        .options(joinedload(OAuthIdentity.user))
    ).one_or_none()


def get_for_user(db: Session, user_id: uuid.UUID, provider: str) -> OAuthIdentity | None:
    return db.scalars(
        select(OAuthIdentity).where(
            OAuthIdentity.user_id == user_id, OAuthIdentity.provider == provider
        )
    ).one_or_none()


def list_for_user(db: Session, user_id: uuid.UUID) -> list[OAuthIdentity]:
    return list(
        db.scalars(
            select(OAuthIdentity)
            .where(OAuthIdentity.user_id == user_id)
            .order_by(OAuthIdentity.created_at)
        )
    )


def count_for_user(db: Session, user_id: uuid.UUID) -> int:
    return (
        db.scalar(
            select(func.count()).select_from(OAuthIdentity).where(OAuthIdentity.user_id == user_id)
        )
        or 0
    )


def create(
    db: Session, *, user_id: uuid.UUID, provider: str, subject: str, now: datetime
) -> OAuthIdentity:
    identity = OAuthIdentity(
        user_id=user_id,
        provider=provider,
        provider_subject=subject,
        created_at=now,
        last_login_at=now,
    )
    db.add(identity)
    db.flush()
    return identity


def delete(db: Session, identity: OAuthIdentity) -> None:
    db.delete(identity)
    db.flush()
