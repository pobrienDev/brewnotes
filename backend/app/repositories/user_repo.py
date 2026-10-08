from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import User


def get(db: Session, user_id: uuid.UUID) -> User | None:
    return db.scalars(
        select(User).where(User.id == user_id).options(selectinload(User.identities))
    ).one_or_none()


def create(db: Session, *, display_name: str, avatar_url: str | None) -> User:
    user = User(display_name=display_name, avatar_url=avatar_url)
    db.add(user)
    db.flush()
    return user


def delete(db: Session, user: User) -> None:
    """Deletes the account; identities and sessions go with it via ON DELETE CASCADE."""
    db.delete(user)
    db.flush()
