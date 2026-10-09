"""Breweries: map queries, search, detail, and the row shape of the upstream CSV."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Annotated

from fastapi import Query
from pydantic import Field, field_validator, model_validator

from app.models.brewery import (
    MAX_ADDRESS,
    MAX_NAME,
    MAX_OBDB_ID,
    MAX_PHONE,
    MAX_PLACE,
    MAX_POSTAL_CODE,
    MAX_TYPE,
    MAX_URL,
)
from app.schemas.base import Schema

BboxParam = Annotated[
    str,
    Query(
        max_length=120,
        description="Visible area as west,south,east,north (min lon, min lat, max lon, max lat)",
    ),
]
TypesParam = Annotated[
    list[str] | None,
    Query(description="Only these brewery types (repeat the parameter); default all but closed"),
]
IncludeClosedParam = Annotated[bool, Query(description="Also return breweries marked closed")]
SearchParam = Annotated[str, Query(min_length=1, max_length=100, description="Name or city")]


@dataclass(frozen=True, slots=True)
class BoundingBox:
    west: float
    south: float
    east: float
    north: float

    @property
    def crosses_antimeridian(self) -> bool:
        return self.west > self.east


def parse_bbox(raw: str) -> BoundingBox:
    """`west,south,east,north`; raises ValueError with a message safe to show."""
    parts = raw.split(",")
    if len(parts) != 4:
        raise ValueError("bbox needs four numbers: west,south,east,north")
    try:
        west, south, east, north = (float(p.strip()) for p in parts)
    except ValueError:
        raise ValueError("bbox values must be numbers") from None
    for value in (west, south, east, north):
        if value != value or value in (float("inf"), float("-inf")):
            raise ValueError("bbox values must be finite")
    if not (-90 <= south <= 90 and -90 <= north <= 90):
        raise ValueError("latitudes must be between -90 and 90")
    if not (-180 <= west <= 180 and -180 <= east <= 180):
        raise ValueError("longitudes must be between -180 and 180")
    if south >= north:
        raise ValueError("south must be less than north")
    return BoundingBox(west, south, east, north)


class BreweryRef(Schema):
    """Enough to name a brewery next to a beer or tasting."""

    id: uuid.UUID
    name: str
    city: str | None
    state_province: str | None
    country: str | None


class BrewerySummary(BreweryRef):
    obdb_id: str
    brewery_type: str
    latitude: float | None
    longitude: float | None
    removed_at: datetime | None = Field(description="Set when it vanished from the upstream data")


class BreweryDetail(BrewerySummary):
    address_1: str | None
    address_2: str | None
    address_3: str | None
    postal_code: str | None
    phone: str | None
    website_url: str | None
    synced_at: datetime


class BreweryMapResult(Schema):
    items: list[BrewerySummary]
    truncated: bool = Field(description="True when more breweries fit the area than returned")
    limit: int


class BreweryTypeCount(Schema):
    brewery_type: str
    count: int


# -- the upstream CSV -----------------------------------------------------------------------


def _blank_to_none(value: object) -> object:
    if isinstance(value, str) and value.strip() == "":
        return None
    return value


class BreweryRow(Schema):
    """One line of Open Brewery DB's breweries.csv after validation."""

    id: str = Field(min_length=1, max_length=MAX_OBDB_ID)
    name: str = Field(min_length=1, max_length=MAX_NAME)
    brewery_type: str = Field(min_length=1, max_length=MAX_TYPE)
    address_1: str | None = Field(default=None, max_length=MAX_ADDRESS)
    address_2: str | None = Field(default=None, max_length=MAX_ADDRESS)
    address_3: str | None = Field(default=None, max_length=MAX_ADDRESS)
    city: str | None = Field(default=None, max_length=MAX_PLACE)
    state_province: str | None = Field(default=None, max_length=MAX_PLACE)
    postal_code: str | None = Field(default=None, max_length=MAX_POSTAL_CODE)
    country: str | None = Field(default=None, max_length=MAX_PLACE)
    phone: str | None = Field(default=None, max_length=MAX_PHONE)
    website_url: str | None = Field(default=None, max_length=MAX_URL)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    latitude: float | None = Field(default=None, ge=-90, le=90)

    @field_validator("*", mode="before")
    @classmethod
    def _blanks(cls, value: object) -> object:
        return _blank_to_none(value)

    @field_validator("brewery_type")
    @classmethod
    def _lowercase_type(cls, value: str) -> str:
        return value.lower()

    @field_validator("website_url")
    @classmethod
    def _http_only(cls, value: str | None) -> str | None:
        if value is not None and not value.startswith(("http://", "https://")):
            return None
        return value

    @model_validator(mode="after")
    def _coordinates_pair(self) -> BreweryRow:
        if (self.latitude is None) != (self.longitude is None):
            self.latitude = None
            self.longitude = None
        return self
