"""Tastings: a rating in half steps and structured notes about a batch or a beer."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, ClassVar

from fastapi import Query
from pydantic import Field, field_validator, model_validator

from app.models.recipe import MAX_NOTES
from app.models.tasting import MAX_TASTING_FIELD, RATING_MAX, RATING_MIN, RATING_STEP
from app.schemas.base import PartialUpdate, Schema
from app.schemas.batches import BatchStatusName, _aware_not_far_future
from app.schemas.breweries import BreweryRef

SubjectParam = Annotated[uuid.UUID | None, Query(description="Only tastings of this subject")]


def _half_steps(value: float | None) -> float | None:
    if value is not None and (value / RATING_STEP) != int(value / RATING_STEP):
        raise ValueError(f"must be in steps of {RATING_STEP}")
    return value


class TastingNotes(Schema):
    aroma: str = Field(default="", max_length=MAX_TASTING_FIELD)
    appearance: str = Field(default="", max_length=MAX_TASTING_FIELD)
    flavor: str = Field(default="", max_length=MAX_TASTING_FIELD)
    mouthfeel: str = Field(default="", max_length=MAX_TASTING_FIELD)
    notes: str = Field(default="", max_length=MAX_NOTES, description="Overall impression")


class TastingCreate(TastingNotes):
    batch_id: uuid.UUID | None = Field(default=None, description="One of batch_id or beer_id")
    beer_id: uuid.UUID | None = None
    rating: float = Field(ge=RATING_MIN, le=RATING_MAX, description="0.5 to 5 in half steps")
    tasted_at: datetime | None = Field(default=None, description="Defaults to now")
    brewery_id: uuid.UUID | None = Field(default=None, description="Where it was tasted")

    @field_validator("rating")
    @classmethod
    def _rating_steps(cls, value: float) -> float:
        _half_steps(value)
        return value

    @field_validator("tasted_at")
    @classmethod
    def _tasted_at_rules(cls, value: datetime | None) -> datetime | None:
        return _aware_not_far_future(value)

    @model_validator(mode="after")
    def _exactly_one_subject(self) -> TastingCreate:
        if (self.batch_id is None) == (self.beer_id is None):
            raise ValueError("give exactly one of batch_id or beer_id")
        return self


class TastingUpdate(PartialUpdate):
    """The subject (batch or beer) is fixed; everything else can change."""

    nullable: ClassVar[frozenset[str]] = frozenset({"brewery_id"})

    rating: float | None = Field(default=None, ge=RATING_MIN, le=RATING_MAX)
    aroma: str | None = Field(default=None, max_length=MAX_TASTING_FIELD)
    appearance: str | None = Field(default=None, max_length=MAX_TASTING_FIELD)
    flavor: str | None = Field(default=None, max_length=MAX_TASTING_FIELD)
    mouthfeel: str | None = Field(default=None, max_length=MAX_TASTING_FIELD)
    notes: str | None = Field(default=None, max_length=MAX_NOTES)
    tasted_at: datetime | None = None
    brewery_id: uuid.UUID | None = None

    @field_validator("rating")
    @classmethod
    def _rating_steps(cls, value: float | None) -> float | None:
        return _half_steps(value)

    @field_validator("tasted_at")
    @classmethod
    def _tasted_at_rules(cls, value: datetime | None) -> datetime | None:
        return _aware_not_far_future(value)


class TastingBatchRef(Schema):
    id: uuid.UUID
    name: str
    status: BatchStatusName


class TastingBeerRef(Schema):
    id: uuid.UUID
    name: str
    brewery_name: str | None


class TastingOut(TastingNotes):
    id: uuid.UUID
    batch: TastingBatchRef | None
    beer: TastingBeerRef | None
    brewery: BreweryRef | None
    rating: float
    tasted_at: datetime
    created_at: datetime
    updated_at: datetime
