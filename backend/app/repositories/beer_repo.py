from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy import Select, func, or_, select, tuple_
from sqlalchemy.orm import Session, selectinload

from app.models import Beer, Style, Tasting


def _loaded() -> Select[Any]:
    return select(Beer).options(
        selectinload(Beer.style).selectinload(Style.ranges),
        selectinload(Beer.style).selectinload(Style.parent),
        selectinload(Beer.brewery),
    )


def list_for_user(
    db: Session,
    user_id: uuid.UUID,
    *,
    search: str | None,
    brewery_id: uuid.UUID | None = None,
    after: tuple[str, uuid.UUID] | None,
    limit: int,
) -> list[Beer]:
    """Alphabetical by name, keyset on (name, id); returns up to limit + 1 rows."""
    query = _loaded().where(Beer.user_id == user_id).order_by(Beer.name, Beer.id).limit(limit + 1)
    if search:
        pattern = f"%{search.strip()}%"
        query = query.where(or_(Beer.name.ilike(pattern), Beer.brewery_name.ilike(pattern)))
    if brewery_id is not None:
        query = query.where(Beer.brewery_id == brewery_id)
    if after is not None:
        query = query.where(tuple_(Beer.name, Beer.id) > tuple_(after[0], after[1]))
    return list(db.scalars(query))


def get(db: Session, user_id: uuid.UUID, beer_id: uuid.UUID) -> Beer | None:
    return db.scalars(_loaded().where(Beer.user_id == user_id, Beer.id == beer_id)).one_or_none()


def count_for_user(db: Session, user_id: uuid.UUID) -> int:
    return db.scalar(select(func.count()).select_from(Beer).where(Beer.user_id == user_id)) or 0


def tasting_stats(
    db: Session, user_id: uuid.UUID, beer_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, tuple[int, float]]:
    """(number of tastings, average rating) per beer that has been tasted."""
    if not beer_ids:
        return {}
    rows = db.execute(
        select(Tasting.beer_id, func.count(), func.avg(Tasting.rating))
        .where(Tasting.user_id == user_id, Tasting.beer_id.in_(beer_ids))
        .group_by(Tasting.beer_id)
    )
    return {beer_id: (count, float(average)) for beer_id, count, average in rows}


def add(db: Session, beer: Beer) -> None:
    db.add(beer)
    db.flush()


def delete(db: Session, beer: Beer) -> None:
    db.delete(beer)
    db.flush()
