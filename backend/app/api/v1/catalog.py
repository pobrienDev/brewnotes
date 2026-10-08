"""Ingredient catalog: built-in items, plus the signed-in user's own. Public, rate limited."""

from __future__ import annotations

import uuid
from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User
from app.schemas.catalog import (
    FermentableOut,
    FermentableUpdate,
    FermentableWrite,
    HopOut,
    HopUpdate,
    HopWrite,
    YeastOut,
    YeastUpdate,
    YeastWrite,
)
from app.schemas.pagination import DEFAULT_LIMIT, CursorParam, LimitParam, Page
from app.security.rate_limit import rate_limit, user_rate_limit
from app.security.sessions import current_user, optional_user
from app.services import catalog_service
from app.services.catalog_service import CatalogType

router = APIRouter(prefix="/catalog", tags=["catalog"])
public_read_rate_limit = rate_limit("public_read", limit=120)
write_rate_limit = user_rate_limit("writes", limit=lambda s: s.write_rate_limit_per_minute)

DB = Annotated[Session, Depends(get_db)]
Me = Annotated[User, Depends(current_user)]


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


# -- custom ingredients: explicit routes per type so request bodies are typed in the spec ---

NO_CONTENT = HTTPStatus.NO_CONTENT
CREATED = HTTPStatus.CREATED
WRITE = [Depends(write_rate_limit)]


@router.post(
    "/fermentables", status_code=CREATED, dependencies=WRITE, summary="Add a custom fermentable"
)
def create_fermentable(
    body: FermentableWrite, request: Request, db: DB, user: Me
) -> FermentableOut:
    item = catalog_service.create_item(
        db, request.app.state.settings, user, CatalogType.FERMENTABLES, body
    )
    return FermentableOut.model_validate(item)


@router.patch("/fermentables/{item_id}", dependencies=WRITE, summary="Edit a custom fermentable")
def update_fermentable(
    item_id: uuid.UUID, body: FermentableUpdate, db: DB, user: Me
) -> FermentableOut:
    item = catalog_service.update_item(db, user, CatalogType.FERMENTABLES, item_id, body)
    return FermentableOut.model_validate(item)


@router.delete(
    "/fermentables/{item_id}",
    status_code=NO_CONTENT,
    dependencies=WRITE,
    summary="Delete a custom fermentable",
)
def delete_fermentable(item_id: uuid.UUID, db: DB, user: Me) -> Response:
    catalog_service.delete_item(db, user, CatalogType.FERMENTABLES, item_id)
    return Response(status_code=NO_CONTENT)


@router.post("/hops", status_code=CREATED, dependencies=WRITE, summary="Add a custom hop")
def create_hop(body: HopWrite, request: Request, db: DB, user: Me) -> HopOut:
    item = catalog_service.create_item(db, request.app.state.settings, user, CatalogType.HOPS, body)
    return HopOut.model_validate(item)


@router.patch("/hops/{item_id}", dependencies=WRITE, summary="Edit a custom hop")
def update_hop(item_id: uuid.UUID, body: HopUpdate, db: DB, user: Me) -> HopOut:
    item = catalog_service.update_item(db, user, CatalogType.HOPS, item_id, body)
    return HopOut.model_validate(item)


@router.delete(
    "/hops/{item_id}", status_code=NO_CONTENT, dependencies=WRITE, summary="Delete a custom hop"
)
def delete_hop(item_id: uuid.UUID, db: DB, user: Me) -> Response:
    catalog_service.delete_item(db, user, CatalogType.HOPS, item_id)
    return Response(status_code=NO_CONTENT)


@router.post("/yeasts", status_code=CREATED, dependencies=WRITE, summary="Add a custom yeast")
def create_yeast(body: YeastWrite, request: Request, db: DB, user: Me) -> YeastOut:
    item = catalog_service.create_item(
        db, request.app.state.settings, user, CatalogType.YEASTS, body
    )
    return YeastOut.model_validate(item)


@router.patch("/yeasts/{item_id}", dependencies=WRITE, summary="Edit a custom yeast")
def update_yeast(item_id: uuid.UUID, body: YeastUpdate, db: DB, user: Me) -> YeastOut:
    item = catalog_service.update_item(db, user, CatalogType.YEASTS, item_id, body)
    return YeastOut.model_validate(item)


@router.delete(
    "/yeasts/{item_id}", status_code=NO_CONTENT, dependencies=WRITE, summary="Delete a custom yeast"
)
def delete_yeast(item_id: uuid.UUID, db: DB, user: Me) -> Response:
    catalog_service.delete_item(db, user, CatalogType.YEASTS, item_id)
    return Response(status_code=NO_CONTENT)
