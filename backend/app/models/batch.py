"""Batches brewed from a recipe, and the gravity/temperature readings logged against them.

A batch freezes the recipe it was brewed from in `recipe_snapshot` (JSONB with a
schema_version, read through `app.schemas.snapshot`), so later edits or deletion of the recipe
never change what was brewed. The optional link back to the recipe is a composite foreign key
(recipe_id, user_id) that the database clears with Postgres's column-list form
`ON DELETE SET NULL (recipe_id)`, leaving user_id intact.

Readings carry user_id and reference (batch_id, user_id), so a reading can never be attached
to another user's batch. They are append-only rows: no updated_at.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Double,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.common import Timestamps, UUIDv7PrimaryKey, now_utc
from app.models.recipe import MAX_NAME, MAX_NOTES, Recipe


class BatchStatus(StrEnum):
    PLANNED = "planned"
    FERMENTING = "fermenting"
    CONDITIONING = "conditioning"
    PACKAGED = "packaged"
    DONE = "done"


class ReadingSource(StrEnum):
    MANUAL = "manual"
    DEVICE = "device"


STATUS_ORDER: tuple[BatchStatus, ...] = tuple(BatchStatus)
GRAVITY_CHECK = "{col} IS NULL OR ({col} >= 0.980 AND {col} <= 1.200)"


class Batch(UUIDv7PrimaryKey, Timestamps, Base):
    __tablename__ = "batches"
    __table_args__ = (
        UniqueConstraint("id", "user_id"),
        ForeignKeyConstraint(
            ["recipe_id", "user_id"],
            ["recipes.id", "recipes.user_id"],
            ondelete="SET NULL (recipe_id)",
        ),
        CheckConstraint(f"char_length(name) BETWEEN 1 AND {MAX_NAME}", name="name_length"),
        CheckConstraint(f"char_length(notes) <= {MAX_NOTES}", name="notes_length"),
        CheckConstraint(
            "status IN ('planned', 'fermenting', 'conditioning', 'packaged', 'done')",
            name="status",
        ),
        CheckConstraint("volume_l >= 0.5 AND volume_l <= 2000", name="volume"),
        CheckConstraint(GRAVITY_CHECK.format(col="measured_og"), name="measured_og"),
        CheckConstraint(GRAVITY_CHECK.format(col="measured_fg"), name="measured_fg"),
        Index("ix_batches_user_id_updated_at", "user_id", "updated_at"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    recipe_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, index=True)
    name: Mapped[str] = mapped_column(String(MAX_NAME), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=BatchStatus.PLANNED.value, server_default="planned"
    )
    brew_date: Mapped[date | None] = mapped_column(Date)
    volume_l: Mapped[float] = mapped_column(Double, nullable=False)
    measured_og: Mapped[float | None] = mapped_column(Double)
    measured_fg: Mapped[float | None] = mapped_column(Double)
    recipe_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # Read-only: the link is maintained through recipe_id so that clearing it never touches
    # user_id (which the composite foreign key also covers).
    recipe: Mapped[Recipe | None] = relationship(
        primaryjoin="Batch.recipe_id == Recipe.id", foreign_keys=[recipe_id], viewonly=True
    )


class Reading(UUIDv7PrimaryKey, Base):
    __tablename__ = "readings"
    __table_args__ = (
        ForeignKeyConstraint(
            ["batch_id", "user_id"], ["batches.id", "batches.user_id"], ondelete="CASCADE"
        ),
        CheckConstraint("gravity_sg IS NOT NULL OR temp_c IS NOT NULL", name="has_a_value"),
        CheckConstraint(GRAVITY_CHECK.format(col="gravity_sg"), name="gravity"),
        CheckConstraint("temp_c IS NULL OR (temp_c >= -10 AND temp_c <= 110)", name="temp"),
        CheckConstraint("source IN ('manual', 'device')", name="source"),
        Index("ix_readings_batch_id_taken_at", "batch_id", "taken_at"),
    )

    batch_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    taken_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    gravity_sg: Mapped[float | None] = mapped_column(Double)
    temp_c: Mapped[float | None] = mapped_column(Double)
    source: Mapped[str] = mapped_column(
        String(16), nullable=False, default=ReadingSource.MANUAL.value, server_default="manual"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=now_utc, server_default=func.now()
    )
