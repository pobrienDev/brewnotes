from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Select, func, select, tuple_
from sqlalchemy.orm import Session, selectinload

from app.models import Recipe, Style


def _loaded() -> Select[Any]:
    return select(Recipe).options(
        selectinload(Recipe.fermentables),
        selectinload(Recipe.hops),
        selectinload(Recipe.yeasts),
        selectinload(Recipe.target_style).selectinload(Style.ranges),
        selectinload(Recipe.target_style).selectinload(Style.parent),
    )


def list_for_user(
    db: Session, user_id: uuid.UUID, *, after: tuple[datetime, uuid.UUID] | None, limit: int
) -> list[Recipe]:
    """Most recently updated first, keyset on (updated_at, id); returns up to limit + 1."""
    query = (
        _loaded()
        .where(Recipe.user_id == user_id)
        .order_by(Recipe.updated_at.desc(), Recipe.id.desc())
        .limit(limit + 1)
    )
    if after is not None:
        query = query.where(tuple_(Recipe.updated_at, Recipe.id) < tuple_(after[0], after[1]))
    return list(db.scalars(query))


def get(db: Session, user_id: uuid.UUID, recipe_id: uuid.UUID) -> Recipe | None:
    return db.scalars(
        _loaded().where(Recipe.user_id == user_id, Recipe.id == recipe_id)
    ).one_or_none()


def count_for_user(db: Session, user_id: uuid.UUID) -> int:
    return db.scalar(select(func.count()).select_from(Recipe).where(Recipe.user_id == user_id)) or 0


def add(db: Session, recipe: Recipe) -> None:
    db.add(recipe)
    db.flush()


def delete(db: Session, recipe: Recipe) -> None:
    db.delete(recipe)
    db.flush()
