"""Commercial beers a user has tasted. Private to that user (decision D6)."""

from __future__ import annotations

import uuid

from sqlalchemy import (
    CheckConstraint,
    Double,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.brewery import Brewery
from app.models.catalog import Style
from app.models.common import Timestamps, UUIDv7PrimaryKey
from app.models.recipe import MAX_NAME, MAX_NOTES


class Beer(UUIDv7PrimaryKey, Timestamps, Base):
    __tablename__ = "beers"
    __table_args__ = (
        UniqueConstraint("id", "user_id"),
        CheckConstraint(f"char_length(name) BETWEEN 1 AND {MAX_NAME}", name="name_length"),
        CheckConstraint(
            f"brewery_name IS NULL OR char_length(brewery_name) BETWEEN 1 AND {MAX_NAME}",
            name="brewery_name_length",
        ),
        CheckConstraint("abv IS NULL OR (abv >= 0 AND abv <= 100)", name="abv"),
        CheckConstraint(f"char_length(notes) <= {MAX_NOTES}", name="notes_length"),
        Index("ix_beers_user_id_name", "user_id", "name"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(MAX_NAME), nullable=False)
    brewery_name: Mapped[str | None] = mapped_column(String(MAX_NAME))
    style_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("styles.id", ondelete="SET NULL"), index=True
    )
    abv: Mapped[float | None] = mapped_column(Double)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # Phase 3: the brewery this beer comes from, when the user linked one (breweries are
    # never hard-deleted; SET NULL is a safety net).
    brewery_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("breweries.id", ondelete="SET NULL"), index=True
    )

    style: Mapped[Style | None] = relationship()
    brewery: Mapped[Brewery | None] = relationship()
