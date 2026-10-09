"""Commercial beers, private to the user who logged them."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, ClassVar

from fastapi import Query
from pydantic import Field

from app.models.recipe import MAX_NAME, MAX_NOTES
from app.schemas.base import PartialUpdate, Schema
from app.schemas.breweries import BreweryRef
from app.schemas.styles import StyleSummary

SearchParam = Annotated[
    str | None, Query(max_length=100, description="Match on the beer or brewery name")
]


class BeerWrite(Schema):
    name: str = Field(min_length=1, max_length=MAX_NAME)
    brewery_name: str | None = Field(default=None, min_length=1, max_length=MAX_NAME)
    style: str | None = Field(default=None, max_length=120, description="Style slug")
    abv: float | None = Field(default=None, ge=0, le=100)
    notes: str = Field(default="", max_length=MAX_NOTES)
    brewery_id: uuid.UUID | None = Field(default=None, description="A brewery from the map")


class BeerUpdate(PartialUpdate):
    nullable: ClassVar[frozenset[str]] = frozenset({"brewery_name", "style", "abv", "brewery_id"})

    name: str | None = Field(default=None, min_length=1, max_length=MAX_NAME)
    brewery_name: str | None = Field(default=None, min_length=1, max_length=MAX_NAME)
    style: str | None = Field(default=None, max_length=120)
    abv: float | None = Field(default=None, ge=0, le=100)
    notes: str | None = Field(default=None, max_length=MAX_NOTES)
    brewery_id: uuid.UUID | None = None


class BeerOut(Schema):
    id: uuid.UUID
    name: str
    brewery_name: str | None
    style: StyleSummary | None
    abv: float | None
    notes: str
    brewery: BreweryRef | None
    tastings_count: int
    average_rating: float | None
    created_at: datetime
    updated_at: datetime
