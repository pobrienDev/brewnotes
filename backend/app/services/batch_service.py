"""Batches: brew a saved recipe, follow its status, log readings and chart fermentation."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from http import HTTPStatus
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.config import Settings
from app.domain import brewmath as bm
from app.domain import fermentation
from app.domain.downsample import carry_forward, lttb_indices
from app.errors import FieldError, ValidationProblemError
from app.models import Batch, Reading, ReadingSource, User
from app.repositories import batch_repo, reading_repo, recipe_repo
from app.schemas.batches import (
    BatchCreate,
    BatchOut,
    BatchSummary,
    BatchUpdate,
    FermentationOut,
    ReadingCreate,
    ReadingOut,
)
from app.schemas.calc import RecipeStatsOut
from app.schemas.pagination import Page, decode_time_cursor, encode_cursor
from app.schemas.snapshot import RecipeSnapshot, RecipeSnapshotV1, parse_snapshot


def _not_found() -> HTTPException:
    return HTTPException(HTTPStatus.NOT_FOUND, detail="No such batch.")


def _reading_not_found() -> HTTPException:
    return HTTPException(HTTPStatus.NOT_FOUND, detail="No such reading.")


def _now() -> datetime:
    return datetime.now(UTC)


def snapshot_of(batch: Batch) -> RecipeSnapshot:
    return parse_snapshot(batch.recipe_snapshot)


def expected_stats(snapshot: RecipeSnapshot) -> bm.RecipeStats:
    return bm.calculate(snapshot.to_domain())


def _fermentation(
    batch: Batch,
    expected: bm.RecipeStats,
    *,
    latest_gravity: Reading | None,
    stats: tuple[int, datetime | None],
) -> FermentationOut:
    progress = fermentation.progress(
        measured_og=batch.measured_og,
        expected_og=expected.og,
        expected_fg=expected.fg,
        measured_fg=batch.measured_fg,
        latest_reading_sg=latest_gravity.gravity_sg if latest_gravity is not None else None,
    )
    count, latest_at = stats
    return FermentationOut.from_domain(progress, readings_count=count, latest_reading_at=latest_at)


def to_out(db: Session, batch: Batch) -> BatchOut:
    snapshot = snapshot_of(batch)
    expected = expected_stats(snapshot)
    latest = reading_repo.latest_gravity_by_batch(db, batch.user_id, [batch.id]).get(batch.id)
    stats = reading_repo.stats_by_batch(db, batch.user_id, [batch.id]).get(batch.id, (0, None))
    return BatchOut(
        id=batch.id,
        recipe_id=batch.recipe_id,
        name=batch.name,
        status=batch.status,  # type: ignore[arg-type]  # CHECK constraint guarantees the set
        brew_date=batch.brew_date,
        volume_l=batch.volume_l,
        measured_og=batch.measured_og,
        measured_fg=batch.measured_fg,
        notes=batch.notes,
        recipe=snapshot,
        expected=RecipeStatsOut.from_domain(expected),
        fermentation=_fermentation(batch, expected, latest_gravity=latest, stats=stats),
        created_at=batch.created_at,
        updated_at=batch.updated_at,
    )


def list_batches(
    db: Session, user: User, *, status: str | None, cursor: str | None, limit: int
) -> Page[BatchSummary]:
    after = decode_time_cursor(cursor) if cursor else None
    rows = batch_repo.list_for_user(db, user.id, status=status, after=after, limit=limit)
    has_more = len(rows) > limit
    rows = rows[:limit]
    ids = [b.id for b in rows]
    latest = reading_repo.latest_gravity_by_batch(db, user.id, ids)
    stats = reading_repo.stats_by_batch(db, user.id, ids)
    items: list[BatchSummary] = []
    for batch in rows:
        snapshot = snapshot_of(batch)
        expected = expected_stats(snapshot)
        items.append(
            BatchSummary(
                id=batch.id,
                recipe_id=batch.recipe_id,
                name=batch.name,
                status=batch.status,  # type: ignore[arg-type]
                brew_date=batch.brew_date,
                volume_l=batch.volume_l,
                recipe_name=snapshot.name,
                target_style_name=snapshot.target_style_name,
                fermentation=_fermentation(
                    batch,
                    expected,
                    latest_gravity=latest.get(batch.id),
                    stats=stats.get(batch.id, (0, None)),
                ),
                updated_at=batch.updated_at,
            )
        )
    next_cursor = (
        encode_cursor(rows[-1].updated_at.isoformat(), rows[-1].id) if has_more and rows else None
    )
    return Page(items=items, next_cursor=next_cursor)


def create(
    db: Session, settings: Settings, user: User, body: BatchCreate, *, now: datetime | None = None
) -> BatchOut:
    if batch_repo.count_for_user(db, user.id) >= settings.quota_batches:
        raise HTTPException(
            HTTPStatus.CONFLICT,
            detail=f"Batch limit reached ({settings.quota_batches}). Delete one to add another.",
        )
    recipe = recipe_repo.get(db, user.id, body.recipe_id)
    if recipe is None:
        raise ValidationProblemError(
            [FieldError(loc=["body", "recipe_id"], msg="unknown recipe", type="value_error")]
        )
    snapshot = RecipeSnapshotV1.from_recipe(recipe, taken_at=now or _now())
    batch = Batch(
        user_id=user.id,
        recipe_id=recipe.id,
        name=body.name or recipe.name,
        status=body.status,
        brew_date=body.brew_date,
        volume_l=body.volume_l if body.volume_l is not None else recipe.batch_volume_l,
        measured_og=body.measured_og,
        measured_fg=body.measured_fg,
        recipe_snapshot=snapshot.to_json(),
        notes=body.notes,
    )
    batch_repo.add(db, batch)
    db.refresh(batch)
    return to_out(db, batch)


def get(db: Session, user: User, batch_id: uuid.UUID) -> BatchOut:
    batch = batch_repo.get(db, user.id, batch_id)
    if batch is None:
        raise _not_found()
    return to_out(db, batch)


def update(db: Session, user: User, batch_id: uuid.UUID, body: BatchUpdate) -> BatchOut:
    batch = batch_repo.get(db, user.id, batch_id)
    if batch is None:
        raise _not_found()
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(batch, field, value)
    db.flush()
    db.refresh(batch)
    return to_out(db, batch)


def delete(db: Session, user: User, batch_id: uuid.UUID) -> None:
    batch = batch_repo.get(db, user.id, batch_id)
    if batch is None:
        raise _not_found()
    batch_repo.delete(db, batch)


# -- readings --------------------------------------------------------------------------------


def add_reading(
    db: Session,
    settings: Settings,
    user: User,
    batch_id: uuid.UUID,
    body: ReadingCreate,
    *,
    now: datetime | None = None,
) -> ReadingOut:
    batch = batch_repo.get(db, user.id, batch_id)
    if batch is None:
        raise _not_found()
    if reading_repo.count_for_batch(db, user.id, batch.id) >= settings.quota_readings_per_batch:
        raise HTTPException(
            HTTPStatus.CONFLICT,
            detail=(f"Reading limit reached for this batch ({settings.quota_readings_per_batch})."),
        )
    reading = Reading(
        batch_id=batch.id,
        user_id=user.id,
        taken_at=body.taken_at or now or _now(),
        gravity_sg=body.gravity_sg,
        temp_c=body.temp_c,
        source=ReadingSource.MANUAL.value,
    )
    reading_repo.add(db, reading)
    db.refresh(reading)
    return ReadingOut.model_validate(reading)


def list_readings(
    db: Session,
    user: User,
    batch_id: uuid.UUID,
    *,
    cursor: str | None,
    limit: int,
    points: int | None,
) -> Page[ReadingOut]:
    batch = batch_repo.get(db, user.id, batch_id)
    if batch is None:
        raise _not_found()
    if points is not None:
        # Chart mode: the whole series, oldest first, thinned to at most `points` readings.
        rows = reading_repo.all_for_batch(db, user.id, batch.id)
        if len(rows) > points:
            xs = [r.taken_at.timestamp() for r in rows]
            ys = carry_forward([r.gravity_sg for r in rows])
            rows = [rows[i] for i in lttb_indices(xs, ys, points)]
        return Page(items=[ReadingOut.model_validate(r) for r in rows], next_cursor=None)
    after = decode_time_cursor(cursor) if cursor else None
    rows = reading_repo.list_for_batch(db, user.id, batch.id, after=after, limit=limit)
    has_more = len(rows) > limit
    rows = rows[:limit]
    next_cursor = (
        encode_cursor(rows[-1].taken_at.isoformat(), rows[-1].id) if has_more and rows else None
    )
    return Page(items=[ReadingOut.model_validate(r) for r in rows], next_cursor=next_cursor)


def delete_reading(db: Session, user: User, batch_id: uuid.UUID, reading_id: uuid.UUID) -> None:
    if batch_repo.get(db, user.id, batch_id) is None:
        raise _not_found()
    reading = reading_repo.get(db, user.id, batch_id, reading_id)
    if reading is None:
        raise _reading_not_found()
    reading_repo.delete(db, reading)


def export_rows(db: Session, user: User) -> list[dict[str, Any]]:
    """Every batch with its snapshot and all of its readings, for the account export."""
    rows: list[dict[str, Any]] = []
    for batch in batch_repo.list_for_user(db, user.id, status=None, after=None, limit=100_000):
        rows.append(
            {
                "id": batch.id,
                "recipe_id": batch.recipe_id,
                "name": batch.name,
                "status": batch.status,
                "brew_date": batch.brew_date,
                "volume_l": batch.volume_l,
                "measured_og": batch.measured_og,
                "measured_fg": batch.measured_fg,
                "notes": batch.notes,
                "recipe_snapshot": batch.recipe_snapshot,
                "readings": [
                    ReadingOut.model_validate(r).model_dump()
                    for r in reading_repo.all_for_batch(db, user.id, batch.id)
                ],
                "created_at": batch.created_at,
                "updated_at": batch.updated_at,
            }
        )
    return rows
