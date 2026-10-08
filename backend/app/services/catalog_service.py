from __future__ import annotations

import uuid
from enum import StrEnum
from http import HTTPStatus

from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.models import Fermentable, Hop, Yeast
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
