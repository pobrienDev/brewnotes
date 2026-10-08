"""Built-in ingredients plus, when a user is given, that user's own entries. Never another
user's."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import Select, or_, select, tuple_
from sqlalchemy.orm import Session

from app.models import Fermentable, Hop, Yeast

CatalogModel = type[Fermentable] | type[Hop] | type[Yeast]


def _visible(model: CatalogModel, user_id: uuid.UUID | None) -> Select[Any]:
    query: Select[Any] = select(model)
    if user_id is None:
        return query.where(model.owner_user_id.is_(None))
    return query.where(or_(model.owner_user_id.is_(None), model.owner_user_id == user_id))


def list_items(
    db: Session,
    model: CatalogModel,
    *,
    user_id: uuid.UUID | None,
    search: str | None,
    after: tuple[str, uuid.UUID] | None,
    limit: int,
) -> list[Fermentable | Hop | Yeast]:
    """Alphabetical, keyset-paginated on (name, id); returns up to limit + 1 rows."""
    query = _visible(model, user_id).order_by(model.name, model.id).limit(limit + 1)
    if search:
        query = query.where(model.name.ilike(f"%{search.strip()}%"))
    if after is not None:
        query = query.where(tuple_(model.name, model.id) > tuple_(after[0], after[1]))
    return list(db.scalars(query))
