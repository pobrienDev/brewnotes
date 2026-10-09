"""Breweries from Open Brewery DB (plan Appendix B), synced by the `sync-breweries` command.

Rows are never hard-deleted: a brewery that disappears upstream gets `removed_at` set and is
hidden from the map, so tastings and beers that point at it keep working. `obdb_id` is the
upstream identifier and the upsert key.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Double, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.common import UUIDv7PrimaryKey, now_utc

MAX_NAME = 200
MAX_OBDB_ID = 64
MAX_TYPE = 32
MAX_ADDRESS = 200
MAX_PLACE = 100
MAX_POSTAL_CODE = 20
MAX_PHONE = 50
MAX_URL = 500

# Upstream's type vocabulary as observed; the column is free text so new values flow through.
BREWERY_TYPES: tuple[str, ...] = (
    "micro",
    "nano",
    "regional",
    "brewpub",
    "large",
    "planning",
    "bar",
    "contract",
    "proprietor",
    "taproom",
    "cidery",
    "beergarden",
    "closed",
)
CLOSED_TYPE = "closed"


class Brewery(UUIDv7PrimaryKey, Base):
    __tablename__ = "breweries"
    __table_args__ = (
        CheckConstraint(f"char_length(name) BETWEEN 1 AND {MAX_NAME}", name="name_length"),
        CheckConstraint(
            f"char_length(brewery_type) BETWEEN 1 AND {MAX_TYPE}", name="brewery_type_length"
        ),
        CheckConstraint(
            "latitude IS NULL OR (latitude >= -90 AND latitude <= 90)", name="latitude"
        ),
        CheckConstraint(
            "longitude IS NULL OR (longitude >= -180 AND longitude <= 180)", name="longitude"
        ),
        CheckConstraint("(latitude IS NULL) = (longitude IS NULL)", name="coordinates_pair"),
        Index("ix_breweries_latitude_longitude", "latitude", "longitude"),
    )

    obdb_id: Mapped[str] = mapped_column(String(MAX_OBDB_ID), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(MAX_NAME), nullable=False)
    brewery_type: Mapped[str] = mapped_column(String(MAX_TYPE), nullable=False, index=True)
    address_1: Mapped[str | None] = mapped_column(String(MAX_ADDRESS))
    address_2: Mapped[str | None] = mapped_column(String(MAX_ADDRESS))
    address_3: Mapped[str | None] = mapped_column(String(MAX_ADDRESS))
    city: Mapped[str | None] = mapped_column(String(MAX_PLACE))
    state_province: Mapped[str | None] = mapped_column(String(MAX_PLACE))
    postal_code: Mapped[str | None] = mapped_column(String(MAX_POSTAL_CODE))
    country: Mapped[str | None] = mapped_column(String(MAX_PLACE))
    latitude: Mapped[float | None] = mapped_column(Double)
    longitude: Mapped[float | None] = mapped_column(Double)
    website_url: Mapped[str | None] = mapped_column(String(MAX_URL))
    phone: Mapped[str | None] = mapped_column(String(MAX_PHONE))
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=now_utc, server_default=func.now()
    )

    @property
    def removed(self) -> bool:
        return self.removed_at is not None
