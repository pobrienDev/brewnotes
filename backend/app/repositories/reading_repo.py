from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import func, select, tuple_
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.orm import Session

from app.models import Reading


def list_for_batch(
    db: Session,
    user_id: uuid.UUID,
    batch_id: uuid.UUID,
    *,
    after: tuple[datetime, uuid.UUID] | None,
    limit: int,
) -> list[Reading]:
    """Newest first, keyset on (taken_at, id); returns up to limit + 1 rows."""
    query = (
        select(Reading)
        .where(Reading.user_id == user_id, Reading.batch_id == batch_id)
        .order_by(Reading.taken_at.desc(), Reading.id.desc())
        .limit(limit + 1)
    )
    if after is not None:
        query = query.where(tuple_(Reading.taken_at, Reading.id) < tuple_(after[0], after[1]))
    return list(db.scalars(query))


def all_for_batch(db: Session, user_id: uuid.UUID, batch_id: uuid.UUID) -> list[Reading]:
    """Every reading, oldest first, for the chart. Bounded by the per-batch quota."""
    return list(
        db.scalars(
            select(Reading)
            .where(Reading.user_id == user_id, Reading.batch_id == batch_id)
            .order_by(Reading.taken_at, Reading.id)
        )
    )


def get(
    db: Session, user_id: uuid.UUID, batch_id: uuid.UUID, reading_id: uuid.UUID
) -> Reading | None:
    return db.scalars(
        select(Reading).where(
            Reading.user_id == user_id, Reading.batch_id == batch_id, Reading.id == reading_id
        )
    ).one_or_none()


def count_for_batch(db: Session, user_id: uuid.UUID, batch_id: uuid.UUID) -> int:
    return (
        db.scalar(
            select(func.count())
            .select_from(Reading)
            .where(Reading.user_id == user_id, Reading.batch_id == batch_id)
        )
        or 0
    )


def latest_gravity_by_batch(
    db: Session, user_id: uuid.UUID, batch_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, Reading]:
    """The most recent reading that carries a gravity, per batch (DISTINCT ON)."""
    if not batch_ids:
        return {}
    rows = db.scalars(
        select(Reading)
        .where(
            Reading.user_id == user_id,
            Reading.batch_id.in_(batch_ids),
            Reading.gravity_sg.is_not(None),
        )
        .ext(distinct_on(Reading.batch_id))
        .order_by(Reading.batch_id, Reading.taken_at.desc(), Reading.id.desc())
    )
    return {row.batch_id: row for row in rows}


def stats_by_batch(
    db: Session, user_id: uuid.UUID, batch_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, tuple[int, datetime | None]]:
    """(count, latest taken_at) per batch, for batches that have any readings."""
    if not batch_ids:
        return {}
    rows = db.execute(
        select(Reading.batch_id, func.count(), func.max(Reading.taken_at))
        .where(Reading.user_id == user_id, Reading.batch_id.in_(batch_ids))
        .group_by(Reading.batch_id)
    )
    return {batch_id: (count, latest) for batch_id, count, latest in rows}


def add(db: Session, reading: Reading) -> None:
    db.add(reading)
    db.flush()


def delete(db: Session, reading: Reading) -> None:
    db.delete(reading)
    db.flush()
