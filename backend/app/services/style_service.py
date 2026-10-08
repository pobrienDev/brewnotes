from __future__ import annotations

import uuid
from http import HTTPStatus

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.repositories import style_repo
from app.schemas.pagination import Page, decode_cursor, encode_cursor
from app.schemas.styles import StyleDetail, StyleSummary


def list_styles(
    db: Session, *, search: str | None, category: str | None, cursor: str | None, limit: int
) -> Page[StyleSummary]:
    after: tuple[int, uuid.UUID] | None = None
    if cursor:
        raw_order, raw_id = decode_cursor(cursor, 2)
        try:
            after = (int(raw_order), uuid.UUID(str(raw_id)))
        except ValueError:
            raise HTTPException(
                HTTPStatus.UNPROCESSABLE_CONTENT, detail="Invalid cursor."
            ) from None
    rows = style_repo.list_styles(db, search=search, category=category, after=after, limit=limit)
    has_more = len(rows) > limit
    rows = rows[:limit]
    next_cursor = encode_cursor(rows[-1].sort_order, rows[-1].id) if has_more and rows else None
    return Page(items=[StyleSummary.from_model(s) for s in rows], next_cursor=next_cursor)


def get_style(db: Session, slug: str) -> StyleDetail:
    style = style_repo.get_by_slug(db, slug)
    if style is None:
        raise HTTPException(HTTPStatus.NOT_FOUND, detail="No such style.")
    return StyleDetail.from_model(style)
