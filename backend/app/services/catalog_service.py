from __future__ import annotations

import uuid
from enum import StrEnum
from http import HTTPStatus
from typing import Any

from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import Fermentable, Hop, User, Yeast
from app.repositories import catalog_repo
from app.schemas.catalog import FermentableOut, HopOut, YeastOut
from app.schemas.pagination import Page, decode_cursor, encode_cursor


class CatalogType(StrEnum):
    FERMENTABLES = "fermentables"
    HOPS = "hops"
    YEASTS = "yeasts"


MODELS: dict[CatalogType, catalog_repo.CatalogModel] = {
    CatalogType.FERMENTABLES: Fermentable,
    CatalogType.HOPS: Hop,
    CatalogType.YEASTS: Yeast,
}
SCHEMAS: dict[CatalogType, type[BaseModel]] = {
    CatalogType.FERMENTABLES: FermentableOut,
    CatalogType.HOPS: HopOut,
    CatalogType.YEASTS: YeastOut,
}


def list_items(
    db: Session,
    kind: CatalogType,
    *,
    user_id: uuid.UUID | None,
    search: str | None,
    cursor: str | None,
    limit: int,
) -> Page[BaseModel]:
    after: tuple[str, uuid.UUID] | None = None
    if cursor:
        raw_name, raw_id = decode_cursor(cursor, 2)
        try:
            after = (str(raw_name), uuid.UUID(str(raw_id)))
        except ValueError:
            raise HTTPException(
                HTTPStatus.UNPROCESSABLE_CONTENT, detail="Invalid cursor."
            ) from None
    rows = catalog_repo.list_items(
        db, MODELS[kind], user_id=user_id, search=search, after=after, limit=limit
    )
    has_more = len(rows) > limit
    rows = rows[:limit]
    next_cursor = encode_cursor(rows[-1].name, rows[-1].id) if has_more and rows else None
    schema = SCHEMAS[kind]
    return Page(items=[schema.model_validate(row) for row in rows], next_cursor=next_cursor)


# -- custom ingredients ----------------------------------------------------------------------


def _not_found(kind: CatalogType) -> HTTPException:
    return HTTPException(HTTPStatus.NOT_FOUND, detail=f"No such custom {kind.value[:-1]}.")


def _duplicate(kind: CatalogType) -> HTTPException:
    return HTTPException(
        HTTPStatus.CONFLICT, detail=f"You already have a {kind.value[:-1]} with that name."
    )


def _flush_or_conflict(db: Session, kind: CatalogType, row: object) -> None:
    """Flush inside a savepoint so a unique-constraint violation becomes a 409 and leaves the
    request's transaction usable."""
    try:
        with db.begin_nested():
            db.flush()
    except IntegrityError as exc:
        if "uq_" in str(exc.orig):
            if row in db:
                db.expunge(row)
            raise _duplicate(kind) from None
        raise


def create_item(
    db: Session, settings: Settings, user: User, kind: CatalogType, body: BaseModel
) -> BaseModel:
    if catalog_repo.count_custom(db, user.id) >= settings.quota_custom_ingredients:
        raise HTTPException(
            HTTPStatus.CONFLICT,
            detail=(
                f"Custom ingredient limit reached ({settings.quota_custom_ingredients}). "
                "Delete one to add another."
            ),
        )
    row = MODELS[kind](owner_user_id=user.id, **body.model_dump())
    db.add(row)
    _flush_or_conflict(db, kind, row)
    return SCHEMAS[kind].model_validate(row)


def update_item(
    db: Session, user: User, kind: CatalogType, item_id: uuid.UUID, body: BaseModel
) -> BaseModel:
    row = catalog_repo.get_owned(db, MODELS[kind], user_id=user.id, item_id=item_id)
    if row is None:
        raise _not_found(kind)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(row, field, value)
    if isinstance(row, Yeast) and row.attenuation_min_pct > row.attenuation_max_pct:
        raise HTTPException(
            HTTPStatus.UNPROCESSABLE_CONTENT,
            detail="attenuation_min_pct must not exceed attenuation_max_pct.",
        )
    _flush_or_conflict(db, kind, row)
    db.refresh(row)
    return SCHEMAS[kind].model_validate(row)


def delete_item(db: Session, user: User, kind: CatalogType, item_id: uuid.UUID) -> None:
    row = catalog_repo.get_owned(db, MODELS[kind], user_id=user.id, item_id=item_id)
    if row is None:
        raise _not_found(kind)
    # Recipes that copied this row keep their snapshot; their reference is set to null by the
    # database.
    db.delete(row)
    db.flush()


def export_custom(db: Session, user: User) -> dict[str, list[dict[str, Any]]]:
    return {
        kind.value: [
            SCHEMAS[kind].model_validate(row).model_dump()
            for row in catalog_repo.list_custom(db, MODELS[kind], user.id)
        ]
        for kind in CatalogType
    }
