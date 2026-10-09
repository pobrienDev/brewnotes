"""Breweries from Open Brewery DB. Public, rate limited per IP."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.breweries import (
    BboxParam,
    BreweryDetail,
    BreweryMapResult,
    BrewerySummary,
    BreweryTypeCount,
    IncludeClosedParam,
    SearchParam,
    TypesParam,
)
from app.schemas.pagination import DEFAULT_LIMIT, CursorParam, LimitParam, Page
from app.security.rate_limit import rate_limit
from app.services import brewery_service

router = APIRouter(prefix="/breweries", tags=["breweries"])
public_read_rate_limit = rate_limit("public_read", limit=120)


@router.get(
    "",
    dependencies=[Depends(public_read_rate_limit)],
    summary="Breweries inside a map area (at most map_max_results; the map clusters them)",
)
def map_breweries(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    bbox: BboxParam,
    type: TypesParam = None,  # the query parameter is called `type`
    include_closed: IncludeClosedParam = False,
) -> BreweryMapResult:
    return brewery_service.map_breweries(
        db, request.app.state.settings, bbox=bbox, types=type, include_closed=include_closed
    )


@router.get(
    "/search",
    dependencies=[Depends(public_read_rate_limit)],
    summary="Search breweries by name or city",
)
def search_breweries(
    db: Annotated[Session, Depends(get_db)],
    q: SearchParam,
    cursor: CursorParam = None,
    limit: LimitParam = DEFAULT_LIMIT,
) -> Page[BrewerySummary]:
    return brewery_service.search(db, q=q, cursor=cursor, limit=limit)


@router.get(
    "/types",
    dependencies=[Depends(public_read_rate_limit)],
    summary="Brewery types with how many breweries each has",
)
def brewery_types(db: Annotated[Session, Depends(get_db)]) -> list[BreweryTypeCount]:
    return brewery_service.type_counts(db)


@router.get("/{brewery_id}", dependencies=[Depends(public_read_rate_limit)], summary="A brewery")
def read_brewery(brewery_id: uuid.UUID, db: Annotated[Session, Depends(get_db)]) -> BreweryDetail:
    return brewery_service.get(db, brewery_id)
