from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Select, and_, func, select, tuple_, union_all
from sqlalchemy.orm import Session, selectinload

from app.models import Batch, Beer, Style, Tasting


def _loaded() -> Select[Any]:
    return select(Tasting).options(
        selectinload(Tasting.batch), selectinload(Tasting.beer), selectinload(Tasting.brewery)
    )


def list_for_user(
    db: Session,
    user_id: uuid.UUID,
    *,
    batch_id: uuid.UUID | None,
    beer_id: uuid.UUID | None,
    brewery_id: uuid.UUID | None = None,
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
    if brewery_id is not None:
        query = query.where(Tasting.brewery_id == brewery_id)
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


def style_ratings(db: Session, user_id: uuid.UUID) -> dict[uuid.UUID, tuple[int, float]]:
    """(number of tastings, average rating) per style the user has tasted: tastings of beers
    that carry a style, and of batches whose recipe snapshot names a target style."""
    via_beer = (
        select(Beer.style_id.label("style_id"), Tasting.rating.label("rating"))
        .select_from(Tasting)
        .join(Beer, and_(Beer.id == Tasting.beer_id, Beer.user_id == Tasting.user_id))
        .where(Tasting.user_id == user_id, Beer.style_id.is_not(None))
    )
    via_batch = (
        select(Style.id.label("style_id"), Tasting.rating.label("rating"))
        .select_from(Tasting)
        .join(Batch, and_(Batch.id == Tasting.batch_id, Batch.user_id == Tasting.user_id))
        .join(Style, Style.slug == Batch.recipe_snapshot["target_style"].astext)
        .where(Tasting.user_id == user_id)
    )
    rated = union_all(via_beer, via_batch).subquery()
    rows = db.execute(
        select(rated.c.style_id, func.count(), func.avg(rated.c.rating)).group_by(rated.c.style_id)
    )
    return {style_id: (count, float(average)) for style_id, count, average in rows}


def add(db: Session, tasting: Tasting) -> None:
    db.add(tasting)
    db.flush()


def delete(db: Session, tasting: Tasting) -> None:
    db.delete(tasting)
    db.flush()
