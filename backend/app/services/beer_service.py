"""Commercial beers: private per user, optionally tied to a style for later recommendations."""

from __future__ import annotations

import uuid
from http import HTTPStatus
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.config import Settings
from app.errors import FieldError, ValidationProblemError
from app.models import Beer, Style, User
from app.repositories import beer_repo, style_repo
from app.schemas.beers import BeerOut, BeerUpdate, BeerWrite
from app.schemas.breweries import BreweryRef
from app.schemas.pagination import Page, decode_name_cursor, encode_cursor
from app.schemas.styles import StyleSummary
from app.services import brewery_service


def _not_found() -> HTTPException:
    return HTTPException(HTTPStatus.NOT_FOUND, detail="No such beer.")


def _resolve_style(db: Session, slug: str | None) -> Style | None:
    if slug is None:
        return None
    style = style_repo.get_by_slug(db, slug)
    if style is None:
        raise ValidationProblemError(
            [FieldError(loc=["body", "style"], msg="unknown style", type="value_error")]
        )
    return style


def to_out(beer: Beer, stats: tuple[int, float] | None) -> BeerOut:
    count, average = stats if stats is not None else (0, None)
    return BeerOut(
        id=beer.id,
        name=beer.name,
        brewery_name=beer.brewery_name,
        style=StyleSummary.from_model(beer.style) if beer.style is not None else None,
        abv=beer.abv,
        notes=beer.notes,
        brewery=BreweryRef.model_validate(beer.brewery) if beer.brewery is not None else None,
        tastings_count=count,
        average_rating=average,
        created_at=beer.created_at,
        updated_at=beer.updated_at,
    )


def _with_stats(db: Session, user: User, beers: list[Beer]) -> list[BeerOut]:
    stats = beer_repo.tasting_stats(db, user.id, [b.id for b in beers])
    return [to_out(b, stats.get(b.id)) for b in beers]


def list_beers(
    db: Session, user: User, *, search: str | None, cursor: str | None, limit: int
) -> Page[BeerOut]:
    after = decode_name_cursor(cursor) if cursor else None
    rows = beer_repo.list_for_user(db, user.id, search=search, after=after, limit=limit)
    has_more = len(rows) > limit
    rows = rows[:limit]
    next_cursor = encode_cursor(rows[-1].name, rows[-1].id) if has_more and rows else None
    return Page(items=_with_stats(db, user, rows), next_cursor=next_cursor)


def _reload(db: Session, user: User, beer_id: uuid.UUID) -> BeerOut:
    beer = beer_repo.get(db, user.id, beer_id)
    assert beer is not None  # noqa: S101  # just written in this transaction
    return _with_stats(db, user, [beer])[0]


def create(db: Session, settings: Settings, user: User, body: BeerWrite) -> BeerOut:
    if beer_repo.count_for_user(db, user.id) >= settings.quota_beers:
        raise HTTPException(
            HTTPStatus.CONFLICT,
            detail=f"Beer limit reached ({settings.quota_beers}). Delete one to add another.",
        )
    style = _resolve_style(db, body.style)
    brewery_service.check_reference(db, body.brewery_id)
    beer = Beer(
        user_id=user.id,
        name=body.name,
        brewery_name=body.brewery_name,
        style_id=style.id if style is not None else None,
        abv=body.abv,
        notes=body.notes,
        brewery_id=body.brewery_id,
    )
    beer_repo.add(db, beer)
    db.expire(beer)
    return _reload(db, user, beer.id)


def get(db: Session, user: User, beer_id: uuid.UUID) -> BeerOut:
    beer = beer_repo.get(db, user.id, beer_id)
    if beer is None:
        raise _not_found()
    return _with_stats(db, user, [beer])[0]


def update(db: Session, user: User, beer_id: uuid.UUID, body: BeerUpdate) -> BeerOut:
    beer = beer_repo.get(db, user.id, beer_id)
    if beer is None:
        raise _not_found()
    changes = body.model_dump(exclude_unset=True)
    if "style" in changes:
        style = _resolve_style(db, changes.pop("style"))
        beer.style_id = style.id if style is not None else None
    if "brewery_id" in changes:
        brewery_service.check_reference(db, changes["brewery_id"])
    for field, value in changes.items():
        setattr(beer, field, value)
    db.flush()
    db.expire(beer)
    return _reload(db, user, beer.id)


def delete(db: Session, user: User, beer_id: uuid.UUID) -> None:
    beer = beer_repo.get(db, user.id, beer_id)
    if beer is None:
        raise _not_found()
    beer_repo.delete(db, beer)


def export_rows(db: Session, user: User) -> list[dict[str, Any]]:
    return [
        {
            "id": beer.id,
            "name": beer.name,
            "brewery_name": beer.brewery_name,
            "style": beer.style.slug if beer.style is not None else None,
            "abv": beer.abv,
            "notes": beer.notes,
            "brewery_id": beer.brewery_id,
            "created_at": beer.created_at,
            "updated_at": beer.updated_at,
        }
        for beer in beer_repo.list_for_user(db, user.id, search=None, after=None, limit=100_000)
    ]
