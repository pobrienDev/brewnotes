"""BJCP styles. Public, rate limited per IP."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.pagination import DEFAULT_LIMIT, CursorParam, LimitParam, Page
from app.schemas.styles import StyleDetail, StyleSummary
from app.security.rate_limit import rate_limit
from app.services import style_service

router = APIRouter(prefix="/styles", tags=["styles"])
public_read_rate_limit = rate_limit("public_read", limit=120)


SearchParam = Annotated[str | None, Query(max_length=100, description="Name or code contains")]
CategoryParam = Annotated[str | None, Query(max_length=8, description="Category code, e.g. 21")]


@router.get("", dependencies=[Depends(public_read_rate_limit)], summary="List styles")
def list_styles(
    db: Annotated[Session, Depends(get_db)],
    search: SearchParam = None,
    category: CategoryParam = None,
    cursor: CursorParam = None,
    limit: LimitParam = DEFAULT_LIMIT,
) -> Page[StyleSummary]:
    return style_service.list_styles(
        db, search=search, category=category, cursor=cursor, limit=limit
    )


@router.get(
    "/{slug}",
    dependencies=[Depends(public_read_rate_limit)],
    summary="Style with ranges and variants",
)
def get_style(slug: str, db: Annotated[Session, Depends(get_db)]) -> StyleDetail:
    return style_service.get_style(db, slug)
