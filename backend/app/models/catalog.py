"""Reference data: BJCP styles with their ranges, and the ingredient catalog.

Catalog rows with a null owner are built-in; otherwise they belong to one user. Recipes copy
the values they use, so editing the catalog never changes a saved recipe.
"""

from __future__ import annotations

import uuid

from sqlalchemy import (
    CheckConstraint,
    Double,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.common import Timestamps, UUIDv7PrimaryKey

MAX_NAME = 200


class Style(UUIDv7PrimaryKey, Timestamps, Base):
    __tablename__ = "styles"

    slug: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    guideline: Mapped[str] = mapped_column(String(16), nullable=False, default="BJCP")
    guideline_version: Mapped[str] = mapped_column(String(16), nullable=False, default="2021")
    category_code: Mapped[str] = mapped_column(String(8), nullable=False)
    category_name: Mapped[str] = mapped_column(String(MAX_NAME), nullable=False)
    # Null where BJCP has no letter code (category 27 historical beers).
    code: Mapped[str | None] = mapped_column(String(8))
    name: Mapped[str] = mapped_column(String(MAX_NAME), nullable=False)
    # Variants (Black IPA under 21B Specialty IPA) point at their parent style.
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("styles.id", ondelete="CASCADE"), index=True
    )
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    source_url: Mapped[str | None] = mapped_column(String(2000))
    # Guideline order: category, code, then variants after their parent.
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    ranges: Mapped[list[StyleRange]] = relationship(
        back_populates="style",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="(StyleRange.metric, StyleRange.min)",
    )
    parent: Mapped[Style | None] = relationship(
        remote_side="Style.id", back_populates="variants", foreign_keys=[parent_id]
    )
    variants: Mapped[list[Style]] = relationship(
        back_populates="parent", order_by="Style.sort_order", foreign_keys=[parent_id]
    )

    @property
    def display_name(self) -> str:
        """'21B Specialty IPA: Black IPA' for variants, '18B American Pale Ale' otherwise."""
        if self.parent is not None:
            return f"{self.parent.display_name}: {self.name}"
        return f"{self.code} {self.name}" if self.code else self.name


class StyleRange(UUIDv7PrimaryKey, Base):
    __tablename__ = "style_ranges"
    __table_args__ = (
        CheckConstraint("metric IN ('og', 'fg', 'abv', 'ibu', 'srm')", name="metric"),
        CheckConstraint('"min" <= "max"', name="min_le_max"),
        UniqueConstraint("style_id", "metric", "label", postgresql_nulls_not_distinct=True),
    )

    style_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("styles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    metric: Mapped[str] = mapped_column(String(8), nullable=False)
    min: Mapped[float] = mapped_column(Double, nullable=False)
    max: Mapped[float] = mapped_column(Double, nullable=False)
    # e.g. Saison's 'table', 'standard', 'super' ABV ranges or 'pale' / 'dark' SRM ranges.
    label: Mapped[str | None] = mapped_column(String(40))

    style: Mapped[Style] = relationship(back_populates="ranges")


class OwnedCatalogRow:
    """Null owner = built-in; otherwise the user's own entry (deleted with the user)."""

    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(MAX_NAME), nullable=False)


class Fermentable(UUIDv7PrimaryKey, OwnedCatalogRow, Timestamps, Base):
    __tablename__ = "fermentables"
    __table_args__ = (
        CheckConstraint("type IN ('grain', 'extract', 'sugar', 'adjunct')", name="type"),
        CheckConstraint("ppg >= 0 AND ppg <= 50", name="ppg_range"),
        CheckConstraint("color_lovibond >= 0 AND color_lovibond <= 700", name="color_range"),
        CheckConstraint(
            "default_addition IN ('mash', 'steep', 'boil', 'fermenter')", name="default_addition"
        ),
        CheckConstraint(f"char_length(name) BETWEEN 1 AND {MAX_NAME}", name="name_length"),
        UniqueConstraint("owner_user_id", "name", postgresql_nulls_not_distinct=True),
    )

    type: Mapped[str] = mapped_column(String(16), nullable=False)
    ppg: Mapped[float] = mapped_column(Double, nullable=False)
    color_lovibond: Mapped[float] = mapped_column(Double, nullable=False)
    default_addition: Mapped[str] = mapped_column(String(16), nullable=False)


class Hop(UUIDv7PrimaryKey, OwnedCatalogRow, Timestamps, Base):
    __tablename__ = "hops"
    __table_args__ = (
        CheckConstraint("alpha_typical_pct >= 0 AND alpha_typical_pct <= 25", name="alpha_range"),
        CheckConstraint(f"char_length(name) BETWEEN 1 AND {MAX_NAME}", name="name_length"),
        UniqueConstraint("owner_user_id", "name", postgresql_nulls_not_distinct=True),
    )

    alpha_typical_pct: Mapped[float] = mapped_column(Double, nullable=False)
    origin: Mapped[str | None] = mapped_column(String(100))


class Yeast(UUIDv7PrimaryKey, OwnedCatalogRow, Timestamps, Base):
    __tablename__ = "yeasts"
    __table_args__ = (
        CheckConstraint(
            "attenuation_min_pct >= 40 AND attenuation_max_pct <= 100 "
            "AND attenuation_min_pct <= attenuation_max_pct",
            name="attenuation_range",
        ),
        CheckConstraint(f"char_length(name) BETWEEN 1 AND {MAX_NAME}", name="name_length"),
        UniqueConstraint("owner_user_id", "lab", "name", postgresql_nulls_not_distinct=True),
    )

    lab: Mapped[str] = mapped_column(String(100), nullable=False)
    product_code: Mapped[str | None] = mapped_column(String(50))
    attenuation_min_pct: Mapped[float] = mapped_column(Double, nullable=False)
    attenuation_max_pct: Mapped[float] = mapped_column(Double, nullable=False)

    @property
    def attenuation_midpoint_pct(self) -> float:
        return (self.attenuation_min_pct + self.attenuation_max_pct) / 2
