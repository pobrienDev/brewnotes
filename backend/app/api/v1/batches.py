"""The signed-in user's batches and their readings. Other users' batches are 404."""

from __future__ import annotations

import uuid
from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User
from app.schemas.batches import (
    BatchCreate,
    BatchOut,
    BatchSummary,
    BatchUpdate,
    PointsParam,
    ReadingCreate,
    ReadingOut,
    StatusParam,
)
from app.schemas.pagination import DEFAULT_LIMIT, CursorParam, LimitParam, Page
from app.security.rate_limit import user_rate_limit
from app.security.sessions import current_user
from app.services import batch_service

router = APIRouter(prefix="/batches", tags=["batches"])
write_rate_limit = user_rate_limit("writes", limit=lambda s: s.write_rate_limit_per_minute)


@router.get("", summary="List my batches, most recently updated first")
def list_batches(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(current_user)],
    status: StatusParam = None,
    cursor: CursorParam = None,
    limit: LimitParam = DEFAULT_LIMIT,
) -> Page[BatchSummary]:
    return batch_service.list_batches(db, user, status=status, cursor=cursor, limit=limit)


@router.post(
    "",
    status_code=HTTPStatus.CREATED,
    dependencies=[Depends(write_rate_limit)],
    summary="Brew a batch from one of my recipes (the recipe is snapshotted)",
)
def create_batch(
    body: BatchCreate,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(current_user)],
) -> BatchOut:
    return batch_service.create(db, request.app.state.settings, user, body)


@router.get("/{batch_id}", summary="A batch with its snapshot, expected numbers and progress")
def read_batch(
    batch_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(current_user)],
) -> BatchOut:
    return batch_service.get(db, user, batch_id)


@router.patch(
    "/{batch_id}",
    dependencies=[Depends(write_rate_limit)],
    summary="Update a batch (status, dates, measured gravities, notes)",
)
def update_batch(
    batch_id: uuid.UUID,
    body: BatchUpdate,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(current_user)],
) -> BatchOut:
    return batch_service.update(db, user, batch_id, body)


@router.delete(
    "/{batch_id}",
    status_code=HTTPStatus.NO_CONTENT,
    dependencies=[Depends(write_rate_limit)],
    summary="Delete a batch with its readings and tastings",
)
def delete_batch(
    batch_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(current_user)],
) -> Response:
    batch_service.delete(db, user, batch_id)
    return Response(status_code=HTTPStatus.NO_CONTENT)


@router.get(
    "/{batch_id}/readings",
    summary="Readings, newest first; or the whole series downsampled with ?points=",
)
def list_readings(
    batch_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(current_user)],
    cursor: CursorParam = None,
    limit: LimitParam = DEFAULT_LIMIT,
    points: PointsParam = None,
) -> Page[ReadingOut]:
    return batch_service.list_readings(
        db, user, batch_id, cursor=cursor, limit=limit, points=points
    )


@router.post(
    "/{batch_id}/readings",
    status_code=HTTPStatus.CREATED,
    dependencies=[Depends(write_rate_limit)],
    summary="Log a gravity and/or temperature reading",
)
def add_reading(
    batch_id: uuid.UUID,
    body: ReadingCreate,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(current_user)],
) -> ReadingOut:
    return batch_service.add_reading(db, request.app.state.settings, user, batch_id, body)


@router.delete(
    "/{batch_id}/readings/{reading_id}",
    status_code=HTTPStatus.NO_CONTENT,
    dependencies=[Depends(write_rate_limit)],
    summary="Remove a mistaken reading",
)
def delete_reading(
    batch_id: uuid.UUID,
    reading_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(current_user)],
) -> Response:
    batch_service.delete_reading(db, user, batch_id, reading_id)
    return Response(status_code=HTTPStatus.NO_CONTENT)
