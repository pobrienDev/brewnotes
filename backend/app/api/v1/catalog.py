"""Ingredient catalog: built-in items, plus the signed-in user's own. Public, rate limited."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User
from app.schemas.catalog import FermentableOut, HopOut, YeastOut
from app.schemas.pagination import DEFAULT_LIMIT, CursorParam, LimitParam, Page
from app.security.rate_limit import rate_limit
from app.security.sessions import optional_user
from app.services import catalog_service
from app.services.catalog_service import CatalogType

router = APIRouter(prefix="/catalog", tags=["catalog"])
public_read_rate_limit = rate_limit("public_read", limit=120)


@router.get(
    "/{kind}",
    dependencies=[Depends(public_read_rate_limit)],
    summary="Search fermentables, hops or yeasts",
    response_model=Page[FermentableOut] | Page[HopOut] | Page[YeastOut],
)
def list_catalog(
    kind: CatalogType,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User | None, Depends(optional_user)],
    q: Annotated[str | None, Query(max_length=100, description="Name contains")] = None,
    cursor: CursorParam = None,
    limit: LimitParam = DEFAULT_LIMIT,
) -> Page[BaseModel]:
    return catalog_service.list_items(
        db, kind, user_id=user.id if user else None, search=q, cursor=cursor, limit=limit
    )
