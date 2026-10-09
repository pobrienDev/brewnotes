"""Batches and their readings (plan Section 5 bounds, Section 6 columns)."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Annotated, ClassVar, Literal

from fastapi import Query
from pydantic import Field, field_validator, model_validator

from app.domain.fermentation import FermentationProgress
from app.models.recipe import MAX_NAME, MAX_NOTES
from app.schemas.base import PartialUpdate, Schema
from app.schemas.calc import RecipeStatsOut
from app.schemas.snapshot import RecipeSnapshotV1

BatchStatusName = Literal["planned", "fermenting", "conditioning", "packaged", "done"]
GravitySourceName = Literal["measured", "estimated", "reading"]
ReadingSourceName = Literal["manual", "device"]

GRAVITY_MIN, GRAVITY_MAX = 0.980, 1.200
TEMP_MIN_C, TEMP_MAX_C = -10.0, 110.0
# Readings may be back-dated freely but not post-dated beyond a small clock-skew allowance.
MAX_FUTURE = timedelta(hours=24)

Gravity = Annotated[float, Field(ge=GRAVITY_MIN, le=GRAVITY_MAX)]
Celsius = Annotated[float, Field(ge=TEMP_MIN_C, le=TEMP_MAX_C)]
PointsParam = Annotated[
    int | None,
    Query(
        ge=2,
        le=1000,
        description=(
            "Downsample to at most this many readings (oldest first) for a chart. "
            "Without it the list is paginated, newest first."
        ),
    ),
]
StatusParam = Annotated[BatchStatusName | None, Query(description="Only batches in this status")]


def _aware_not_far_future(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("must include a timezone offset, e.g. 2026-10-08T18:30:00Z")
    if value > datetime.now(UTC) + MAX_FUTURE:
        raise ValueError("may not be more than a day in the future")
    return value


class BatchCreate(Schema):
    recipe_id: uuid.UUID = Field(description="The saved recipe to brew; it is snapshotted")
    name: str | None = Field(
        default=None, min_length=1, max_length=MAX_NAME, description="Defaults to the recipe name"
    )
    status: BatchStatusName = "planned"
    brew_date: date | None = None
    volume_l: float | None = Field(
        default=None, ge=0.5, le=2000, description="Defaults to the recipe's batch volume"
    )
    measured_og: Gravity | None = None
    measured_fg: Gravity | None = None
    notes: str = Field(default="", max_length=MAX_NOTES)


class BatchUpdate(PartialUpdate):
    nullable: ClassVar[frozenset[str]] = frozenset({"brew_date", "measured_og", "measured_fg"})

    name: str | None = Field(default=None, min_length=1, max_length=MAX_NAME)
    status: BatchStatusName | None = None
    brew_date: date | None = None
    volume_l: float | None = Field(default=None, ge=0.5, le=2000)
    measured_og: Gravity | None = None
    measured_fg: Gravity | None = None
    notes: str | None = Field(default=None, max_length=MAX_NOTES)


class FermentationOut(Schema):
    """Where fermentation stands, from the brewer's measurements and the logged readings."""

    og: float
    og_source: GravitySourceName
    current_sg: float | None
    current_sg_source: GravitySourceName | None
    apparent_attenuation_pct: float | None
    abv: float | None
    expected_fg: float
    expected_attenuation_pct: float | None
    readings_count: int
    latest_reading_at: datetime | None

    @classmethod
    def from_domain(
        cls,
        progress: FermentationProgress,
        *,
        readings_count: int,
        latest_reading_at: datetime | None,
    ) -> FermentationOut:
        return cls(
            og=progress.og,
            og_source=progress.og_source.value,
            current_sg=progress.current_sg,
            current_sg_source=(
                progress.current_sg_source.value if progress.current_sg_source else None
            ),
            apparent_attenuation_pct=progress.apparent_attenuation_pct,
            abv=progress.abv,
            expected_fg=progress.expected_fg,
            expected_attenuation_pct=progress.expected_attenuation_pct,
            readings_count=readings_count,
            latest_reading_at=latest_reading_at,
        )


class BatchOut(Schema):
    id: uuid.UUID
    recipe_id: uuid.UUID | None = Field(description="Null once the recipe has been deleted")
    name: str
    status: BatchStatusName
    brew_date: date | None
    volume_l: float
    measured_og: float | None
    measured_fg: float | None
    notes: str
    recipe: RecipeSnapshotV1 = Field(description="The recipe as it was when the batch was made")
    expected: RecipeStatsOut = Field(description="Calculator output for the snapshot")
    fermentation: FermentationOut
    created_at: datetime
    updated_at: datetime


class BatchSummary(Schema):
    id: uuid.UUID
    recipe_id: uuid.UUID | None
    name: str
    status: BatchStatusName
    brew_date: date | None
    volume_l: float
    recipe_name: str
    target_style_name: str | None
    fermentation: FermentationOut
    updated_at: datetime


class ReadingCreate(Schema):
    taken_at: datetime | None = Field(
        default=None, description="When the reading was taken; defaults to now"
    )
    gravity_sg: Gravity | None = None
    temp_c: Celsius | None = None

    @field_validator("taken_at")
    @classmethod
    def _taken_at_rules(cls, value: datetime | None) -> datetime | None:
        return _aware_not_far_future(value)

    @model_validator(mode="after")
    def _has_a_value(self) -> ReadingCreate:
        if self.gravity_sg is None and self.temp_c is None:
            raise ValueError("a reading needs a gravity, a temperature, or both")
        return self


class ReadingOut(Schema):
    id: uuid.UUID
    taken_at: datetime
    gravity_sg: float | None
    temp_c: float | None
    source: ReadingSourceName
    created_at: datetime
