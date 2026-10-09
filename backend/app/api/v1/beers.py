"""The signed-in user's commercial beers. Private: other users' beers are 404."""

from __future__ import annotations

import uuid
from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User
from app.schemas.beers import BeerOut, BeerUpdate, BeerWrite, SearchParam
from app.schemas.pagination import DEFAULT_LIMIT, CursorParam, LimitParam, Page
from app.security.rate_limit import user_rate_limit
from app.security.sessions import current_user
from app.services import beer_service

router = APIRouter(prefix="/beers", tags=["beers"])
write_rate_limit = user_rate_limit("writes", limit=lambda s: s.write_rate_limit_per_minute)


@router.get("", summary="List my beers alphabetically")
def list_beers(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(current_user)],
    q: SearchParam = None,
    cursor: CursorParam = None,
    limit: LimitParam = DEFAULT_LIMIT,
) -> Page[BeerOut]:
    return beer_service.list_beers(db, user, search=q, cursor=cursor, limit=limit)


@router.post(
    "",
    status_code=HTTPStatus.CREATED,
    dependencies=[Depends(write_rate_limit)],
    summary="Add a commercial beer",
)
def create_beer(
    body: BeerWrite,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(current_user)],
) -> BeerOut:
    return beer_service.create(db, request.app.state.settings, user, body)


@router.get("/{beer_id}", summary="A beer with its tasting count and average rating")
def read_beer(
    beer_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(current_user)],
) -> BeerOut:
    return beer_service.get(db, user, beer_id)


@router.patch("/{beer_id}", dependencies=[Depends(write_rate_limit)], summary="Update a beer")
def update_beer(
    beer_id: uuid.UUID,
    body: BeerUpdate,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(current_user)],
) -> BeerOut:
    return beer_service.update(db, user, beer_id, body)


@router.delete(
    "/{beer_id}",
    status_code=HTTPStatus.NO_CONTENT,
    dependencies=[Depends(write_rate_limit)],
    summary="Delete a beer and its tastings",
)
def delete_beer(
    beer_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(current_user)],
) -> Response:
    beer_service.delete(db, user, beer_id)
    return Response(status_code=HTTPStatus.NO_CONTENT)
