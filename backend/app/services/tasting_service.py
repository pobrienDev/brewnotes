"""Tastings of the user's own batches and beers."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from http import HTTPStatus
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.config import Settings
from app.errors import FieldError, ValidationProblemError
from app.models import Tasting, User
from app.repositories import batch_repo, beer_repo, tasting_repo
from app.schemas.pagination import Page, decode_time_cursor, encode_cursor
from app.schemas.tastings import (
    TastingBatchRef,
    TastingBeerRef,
    TastingCreate,
    TastingOut,
    TastingUpdate,
)


def _not_found() -> HTTPException:
    return HTTPException(HTTPStatus.NOT_FOUND, detail="No such tasting.")


def to_out(tasting: Tasting) -> TastingOut:
    return TastingOut(
        id=tasting.id,
        batch=TastingBatchRef.model_validate(tasting.batch) if tasting.batch else None,
        beer=TastingBeerRef.model_validate(tasting.beer) if tasting.beer else None,
        rating=tasting.rating,
        aroma=tasting.aroma,
        appearance=tasting.appearance,
        flavor=tasting.flavor,
        mouthfeel=tasting.mouthfeel,
        notes=tasting.notes,
        tasted_at=tasting.tasted_at,
        created_at=tasting.created_at,
        updated_at=tasting.updated_at,
    )


def list_tastings(
    db: Session,
    user: User,
    *,
    batch_id: uuid.UUID | None,
    beer_id: uuid.UUID | None,
    cursor: str | None,
    limit: int,
) -> Page[TastingOut]:
    after = decode_time_cursor(cursor) if cursor else None
    rows = tasting_repo.list_for_user(
        db, user.id, batch_id=batch_id, beer_id=beer_id, after=after, limit=limit
    )
    has_more = len(rows) > limit
    rows = rows[:limit]
    next_cursor = (
        encode_cursor(rows[-1].tasted_at.isoformat(), rows[-1].id) if has_more and rows else None
    )
    return Page(items=[to_out(t) for t in rows], next_cursor=next_cursor)


def _check_subject(db: Session, user: User, body: TastingCreate) -> None:
    """The batch or beer must be the caller's own; anything else is an unknown reference."""
    if body.batch_id is not None and batch_repo.get(db, user.id, body.batch_id) is None:
        raise ValidationProblemError(
            [FieldError(loc=["body", "batch_id"], msg="unknown batch", type="value_error")]
        )
    if body.beer_id is not None and beer_repo.get(db, user.id, body.beer_id) is None:
        raise ValidationProblemError(
            [FieldError(loc=["body", "beer_id"], msg="unknown beer", type="value_error")]
        )


def _reload(db: Session, user: User, tasting_id: uuid.UUID) -> TastingOut:
    tasting = tasting_repo.get(db, user.id, tasting_id)
    assert tasting is not None  # noqa: S101  # just written in this transaction
    return to_out(tasting)


def create(
    db: Session,
    settings: Settings,
    user: User,
    body: TastingCreate,
    *,
    now: datetime | None = None,
) -> TastingOut:
    if tasting_repo.count_for_user(db, user.id) >= settings.quota_tastings:
        raise HTTPException(
            HTTPStatus.CONFLICT,
            detail=(
                f"Tasting limit reached ({settings.quota_tastings}). Delete one to add another."
            ),
        )
    _check_subject(db, user, body)
    tasting = Tasting(
        user_id=user.id,
        batch_id=body.batch_id,
        beer_id=body.beer_id,
        rating=body.rating,
        aroma=body.aroma,
        appearance=body.appearance,
        flavor=body.flavor,
        mouthfeel=body.mouthfeel,
        notes=body.notes,
        tasted_at=body.tasted_at or now or datetime.now(UTC),
    )
    tasting_repo.add(db, tasting)
    db.expire(tasting)
    return _reload(db, user, tasting.id)


def get(db: Session, user: User, tasting_id: uuid.UUID) -> TastingOut:
    tasting = tasting_repo.get(db, user.id, tasting_id)
    if tasting is None:
        raise _not_found()
    return to_out(tasting)


def update(db: Session, user: User, tasting_id: uuid.UUID, body: TastingUpdate) -> TastingOut:
    tasting = tasting_repo.get(db, user.id, tasting_id)
    if tasting is None:
        raise _not_found()
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(tasting, field, value)
    db.flush()
    db.expire(tasting)
    return _reload(db, user, tasting.id)


def delete(db: Session, user: User, tasting_id: uuid.UUID) -> None:
    tasting = tasting_repo.get(db, user.id, tasting_id)
    if tasting is None:
        raise _not_found()
    tasting_repo.delete(db, tasting)


def export_rows(db: Session, user: User) -> list[dict[str, Any]]:
    return [
        {
            "id": t.id,
            "batch_id": t.batch_id,
            "beer_id": t.beer_id,
            "rating": t.rating,
            "aroma": t.aroma,
            "appearance": t.appearance,
            "flavor": t.flavor,
            "mouthfeel": t.mouthfeel,
            "notes": t.notes,
            "tasted_at": t.tasted_at,
            "created_at": t.created_at,
            "updated_at": t.updated_at,
        }
        for t in tasting_repo.list_for_user(
            db, user.id, batch_id=None, beer_id=None, after=None, limit=100_000
        )
    ]
