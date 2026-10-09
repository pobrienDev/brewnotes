from __future__ import annotations

import uuid
from collections.abc import Iterable, Sequence
from datetime import datetime
from typing import Any, cast

from sqlalchemy import CursorResult, and_, func, or_, select, tuple_, update
from sqlalchemy.orm import Session

from app.models import Brewery
from app.models.brewery import CLOSED_TYPE
from app.schemas.breweries import BoundingBox


def get(db: Session, brewery_id: uuid.UUID) -> Brewery | None:
    return db.get(Brewery, brewery_id)


def in_bbox(
    db: Session,
    bbox: BoundingBox,
    *,
    types: Sequence[str] | None,
    include_closed: bool,
    limit: int,
) -> list[Brewery]:
    """Breweries with coordinates inside the box, present upstream; up to limit + 1 rows."""
    if bbox.crosses_antimeridian:
        lon_clause = or_(Brewery.longitude >= bbox.west, Brewery.longitude <= bbox.east)
    else:
        lon_clause = and_(Brewery.longitude >= bbox.west, Brewery.longitude <= bbox.east)
    query = (
        select(Brewery)
        .where(
            Brewery.removed_at.is_(None),
            Brewery.latitude >= bbox.south,
            Brewery.latitude <= bbox.north,
            lon_clause,
        )
        .order_by(Brewery.id)
        .limit(limit + 1)
    )
    if types:
        query = query.where(Brewery.brewery_type.in_(types))
    elif not include_closed:
        query = query.where(Brewery.brewery_type != CLOSED_TYPE)
    return list(db.scalars(query))


def search(
    db: Session, text: str, *, after: tuple[str, uuid.UUID] | None, limit: int
) -> list[Brewery]:
    """Name or city contains the text; alphabetical keyset on (name, id); limit + 1 rows."""
    pattern = f"%{text.strip()}%"
    query = (
        select(Brewery)
        .where(
            Brewery.removed_at.is_(None),
            or_(Brewery.name.ilike(pattern), Brewery.city.ilike(pattern)),
        )
        .order_by(Brewery.name, Brewery.id)
        .limit(limit + 1)
    )
    if after is not None:
        query = query.where(tuple_(Brewery.name, Brewery.id) > tuple_(after[0], after[1]))
    return list(db.scalars(query))


def type_counts(db: Session) -> list[tuple[str, int]]:
    rows = db.execute(
        select(Brewery.brewery_type, func.count())
        .where(Brewery.removed_at.is_(None))
        .group_by(Brewery.brewery_type)
        .order_by(func.count().desc(), Brewery.brewery_type)
    )
    return [(brewery_type, count) for brewery_type, count in rows]


def by_obdb_ids(db: Session, obdb_ids: Iterable[str]) -> dict[str, Brewery]:
    ids = list(obdb_ids)
    found: dict[str, Brewery] = {}
    for start in range(0, len(ids), 1000):
        chunk = ids[start : start + 1000]
        for row in db.scalars(select(Brewery).where(Brewery.obdb_id.in_(chunk))):
            found[row.obdb_id] = row
    return found


def mark_removed_except(db: Session, present_obdb_ids: Sequence[str], now: datetime) -> int:
    """Flag every row that is not in the upstream data any more; returns how many."""
    statement = update(Brewery).where(Brewery.removed_at.is_(None)).values(removed_at=now)
    if present_obdb_ids:
        statement = statement.where(Brewery.obdb_id.not_in(present_obdb_ids))
    result = cast(CursorResult[Any], db.execute(statement))
    return int(result.rowcount or 0)


def counts(db: Session) -> tuple[int, int]:
    """(present, removed)."""
    present = db.scalar(
        select(func.count()).select_from(Brewery).where(Brewery.removed_at.is_(None))
    )
    removed = db.scalar(
        select(func.count()).select_from(Brewery).where(Brewery.removed_at.is_not(None))
    )
    return int(present or 0), int(removed or 0)


def add_all(db: Session, rows: Iterable[Brewery]) -> None:
    db.add_all(rows)
    db.flush()
