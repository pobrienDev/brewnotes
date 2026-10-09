from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Select, func, select, tuple_
from sqlalchemy.orm import Session, selectinload

from app.models import Tasting


def _loaded() -> Select[Any]:
    return select(Tasting).options(selectinload(Tasting.batch), selectinload(Tasting.beer))


def list_for_user(
    db: Session,
    user_id: uuid.UUID,
    *,
    batch_id: uuid.UUID | None,
    beer_id: uuid.UUID | None,
    after: tuple[datetime, uuid.UUID] | None,
    limit: int,
) -> list[Tasting]:
    """Most recent tasting first, keyset on (tasted_at, id); returns up to limit + 1 rows."""
    query = (
        _loaded()
        .where(Tasting.user_id == user_id)
        .order_by(Tasting.tasted_at.desc(), Tasting.id.desc())
        .limit(limit + 1)
    )
    if batch_id is not None:
        query = query.where(Tasting.batch_id == batch_id)
    if beer_id is not None:
        query = query.where(Tasting.beer_id == beer_id)
    if after is not None:
        query = query.where(tuple_(Tasting.tasted_at, Tasting.id) < tuple_(after[0], after[1]))
    return list(db.scalars(query))


def get(db: Session, user_id: uuid.UUID, tasting_id: uuid.UUID) -> Tasting | None:
    return db.scalars(
        _loaded().where(Tasting.user_id == user_id, Tasting.id == tasting_id)
    ).one_or_none()


def count_for_user(db: Session, user_id: uuid.UUID) -> int:
    return (
        db.scalar(select(func.count()).select_from(Tasting).where(Tasting.user_id == user_id)) or 0
    )


def add(db: Session, tasting: Tasting) -> None:
    db.add(tasting)
    db.flush()


def delete(db: Session, tasting: Tasting) -> None:
    db.delete(tasting)
    db.flush()
