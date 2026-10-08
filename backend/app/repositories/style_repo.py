from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import or_, select, tuple_
from sqlalchemy.orm import Session, selectinload

from app.models import Style


def _base() -> Any:
    return select(Style).options(selectinload(Style.ranges), selectinload(Style.parent))


def list_styles(
    db: Session,
    *,
    search: str | None,
    category: str | None,
    after: tuple[int, uuid.UUID] | None,
    limit: int,
) -> list[Style]:
    """Guideline order, keyset-paginated on (sort_order, id); returns up to limit + 1 rows so
    the caller knows whether another page exists."""
    query = _base().order_by(Style.sort_order, Style.id).limit(limit + 1)
    if search:
        pattern = f"%{search.strip()}%"
        query = query.where(or_(Style.name.ilike(pattern), Style.code.ilike(pattern)))
    if category:
        query = query.where(Style.category_code == category.strip())
    if after is not None:
        query = query.where(tuple_(Style.sort_order, Style.id) > tuple_(after[0], after[1]))
    return list(db.scalars(query))


def get_by_slug(db: Session, slug: str) -> Style | None:
    query = (
        _base()
        .options(selectinload(Style.variants).selectinload(Style.ranges))
        .where(Style.slug == slug)
    )
    return db.scalars(query).one_or_none()


def all_with_ranges(db: Session) -> Sequence[Style]:
    return db.scalars(_base().where(Style.ranges.any()).order_by(Style.sort_order)).all()


def exists(db: Session, slug: str) -> bool:
    return db.scalar(select(Style.id).where(Style.slug == slug)) is not None


from typing import Any  # noqa: E402
