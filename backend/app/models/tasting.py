"""Tastings: a rating and structured notes for either one of the user's batches or one of
their beers, never both and never neither (CHECK). Both links are composite foreign keys
carrying user_id, so a tasting cannot reference another user's batch or beer."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Double,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.batch import Batch
from app.models.beer import Beer
from app.models.common import Timestamps, UUIDv7PrimaryKey, now_utc
from app.models.recipe import MAX_NOTES

MAX_TASTING_FIELD = 2000
RATING_MIN = 0.5
RATING_MAX = 5.0
RATING_STEP = 0.5


class Tasting(UUIDv7PrimaryKey, Timestamps, Base):
    __tablename__ = "tastings"
    __table_args__ = (
        ForeignKeyConstraint(
            ["batch_id", "user_id"], ["batches.id", "batches.user_id"], ondelete="CASCADE"
        ),
        ForeignKeyConstraint(
            ["beer_id", "user_id"], ["beers.id", "beers.user_id"], ondelete="CASCADE"
        ),
        CheckConstraint("(batch_id IS NULL) <> (beer_id IS NULL)", name="exactly_one_subject"),
        CheckConstraint(
            "rating >= 0.5 AND rating <= 5 AND rating * 2 = floor(rating * 2)", name="rating"
        ),
        CheckConstraint(f"char_length(aroma) <= {MAX_TASTING_FIELD}", name="aroma_length"),
        CheckConstraint(
            f"char_length(appearance) <= {MAX_TASTING_FIELD}", name="appearance_length"
        ),
        CheckConstraint(f"char_length(flavor) <= {MAX_TASTING_FIELD}", name="flavor_length"),
        CheckConstraint(f"char_length(mouthfeel) <= {MAX_TASTING_FIELD}", name="mouthfeel_length"),
        CheckConstraint(f"char_length(notes) <= {MAX_NOTES}", name="notes_length"),
        Index("ix_tastings_user_id_tasted_at", "user_id", "tasted_at"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    batch_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, index=True)
    beer_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, index=True)
    rating: Mapped[float] = mapped_column(Double, nullable=False)
    aroma: Mapped[str] = mapped_column(Text, nullable=False, default="")
    appearance: Mapped[str] = mapped_column(Text, nullable=False, default="")
    flavor: Mapped[str] = mapped_column(Text, nullable=False, default="")
    mouthfeel: Mapped[str] = mapped_column(Text, nullable=False, default="")
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    tasted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=now_utc, server_default=func.now()
    )

    # Read-only views of the subject; the service sets batch_id / beer_id directly so that
    # clearing a link can never also clear user_id.
    batch: Mapped[Batch | None] = relationship(
        primaryjoin="Tasting.batch_id == Batch.id", foreign_keys=[batch_id], viewonly=True
    )
    beer: Mapped[Beer | None] = relationship(
        primaryjoin="Tasting.beer_id == Beer.id", foreign_keys=[beer_id], viewonly=True
    )
