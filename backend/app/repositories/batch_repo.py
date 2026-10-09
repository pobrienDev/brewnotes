from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import func, select, tuple_
from sqlalchemy.orm import Session

from app.models import Batch


def list_for_user(
    db: Session,
    user_id: uuid.UUID,
    *,
    status: str | None,
    after: tuple[datetime, uuid.UUID] | None,
    limit: int,
) -> list[Batch]:
    """Most recently updated first, keyset on (updated_at, id); returns up to limit + 1."""
    query = (
        select(Batch)
        .where(Batch.user_id == user_id)
        .order_by(Batch.updated_at.desc(), Batch.id.desc())
        .limit(limit + 1)
    )
    if status is not None:
        query = query.where(Batch.status == status)
    if after is not None:
        query = query.where(tuple_(Batch.updated_at, Batch.id) < tuple_(after[0], after[1]))
    return list(db.scalars(query))


def get(db: Session, user_id: uuid.UUID, batch_id: uuid.UUID) -> Batch | None:
    return db.scalars(
        select(Batch).where(Batch.user_id == user_id, Batch.id == batch_id)
    ).one_or_none()


def count_for_user(db: Session, user_id: uuid.UUID) -> int:
    return db.scalar(select(func.count()).select_from(Batch).where(Batch.user_id == user_id)) or 0


def add(db: Session, batch: Batch) -> None:
    db.add(batch)
    db.flush()


def delete(db: Session, batch: Batch) -> None:
    db.delete(batch)
    db.flush()
