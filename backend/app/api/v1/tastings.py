"""The signed-in user's tastings of their own batches and beers."""

from __future__ import annotations

import uuid
from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User
from app.schemas.pagination import DEFAULT_LIMIT, CursorParam, LimitParam, Page
from app.schemas.tastings import SubjectParam, TastingCreate, TastingOut, TastingUpdate
from app.security.rate_limit import user_rate_limit
from app.security.sessions import current_user
from app.services import tasting_service

router = APIRouter(prefix="/tastings", tags=["tastings"])
write_rate_limit = user_rate_limit("writes", limit=lambda s: s.write_rate_limit_per_minute)


@router.get("", summary="List my tastings, most recent first")
def list_tastings(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(current_user)],
    batch_id: SubjectParam = None,
    beer_id: SubjectParam = None,
    brewery_id: SubjectParam = None,
    cursor: CursorParam = None,
    limit: LimitParam = DEFAULT_LIMIT,
) -> Page[TastingOut]:
    return tasting_service.list_tastings(
        db,
        user,
        batch_id=batch_id,
        beer_id=beer_id,
        brewery_id=brewery_id,
        cursor=cursor,
        limit=limit,
    )


@router.post(
    "",
    status_code=HTTPStatus.CREATED,
    dependencies=[Depends(write_rate_limit)],
    summary="Rate one of my batches or beers",
)
def create_tasting(
    body: TastingCreate,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(current_user)],
) -> TastingOut:
    return tasting_service.create(db, request.app.state.settings, user, body)


@router.get("/{tasting_id}", summary="A tasting")
def read_tasting(
    tasting_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(current_user)],
) -> TastingOut:
    return tasting_service.get(db, user, tasting_id)


@router.patch("/{tasting_id}", dependencies=[Depends(write_rate_limit)], summary="Update a tasting")
def update_tasting(
    tasting_id: uuid.UUID,
    body: TastingUpdate,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(current_user)],
) -> TastingOut:
    return tasting_service.update(db, user, tasting_id, body)


@router.delete(
    "/{tasting_id}",
    status_code=HTTPStatus.NO_CONTENT,
    dependencies=[Depends(write_rate_limit)],
    summary="Delete a tasting",
)
def delete_tasting(
    tasting_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(current_user)],
) -> Response:
    tasting_service.delete(db, user, tasting_id)
    return Response(status_code=HTTPStatus.NO_CONTENT)
