"""Recipes and their ingredient rows.

Ingredient rows copy the values they use (name, PPG, colour, alpha, attenuation) so catalog
edits never change a saved recipe; the catalog reference is kept only as a pointer. Children
carry user_id and reference (recipe_id, user_id) so the database itself refuses a row that
points at another user's recipe.
"""

from __future__ import annotations

import uuid

from sqlalchemy import (
    CheckConstraint,
    Double,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.catalog import Style
from app.models.common import Timestamps, UUIDv7PrimaryKey

MAX_NAME = 200
MAX_NOTES = 10_000


class Recipe(UUIDv7PrimaryKey, Timestamps, Base):
    __tablename__ = "recipes"
    __table_args__ = (
        # Lets child tables reference (recipe_id, user_id) with a composite foreign key.
        UniqueConstraint("id", "user_id"),
        CheckConstraint(f"char_length(name) BETWEEN 1 AND {MAX_NAME}", name="name_length"),
        CheckConstraint(f"char_length(notes) <= {MAX_NOTES}", name="notes_length"),
        CheckConstraint("batch_volume_l >= 0.5 AND batch_volume_l <= 2000", name="batch_volume"),
        CheckConstraint(
            "pre_boil_volume_l IS NULL "
            "OR (pre_boil_volume_l >= batch_volume_l AND pre_boil_volume_l <= 2500)",
            name="pre_boil_volume",
        ),
        CheckConstraint("boil_time_min >= 0 AND boil_time_min <= 360", name="boil_time"),
        CheckConstraint(
            "brewhouse_efficiency_pct >= 20 AND brewhouse_efficiency_pct <= 100",
            name="brewhouse_efficiency",
        ),
        CheckConstraint(
            "steep_efficiency_pct >= 20 AND steep_efficiency_pct <= 100", name="steep_efficiency"
        ),
        Index("ix_recipes_user_id_updated_at", "user_id", "updated_at"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(MAX_NAME), nullable=False)
    target_style_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("styles.id", ondelete="SET NULL"), index=True
    )
    batch_volume_l: Mapped[float] = mapped_column(Double, nullable=False)
    pre_boil_volume_l: Mapped[float | None] = mapped_column(Double)
    boil_time_min: Mapped[float] = mapped_column(Double, nullable=False)
    brewhouse_efficiency_pct: Mapped[float] = mapped_column(Double, nullable=False, default=72)
    steep_efficiency_pct: Mapped[float] = mapped_column(Double, nullable=False, default=50)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")

    target_style: Mapped[Style | None] = relationship()
    fermentables: Mapped[list[RecipeFermentable]] = relationship(
        back_populates="recipe",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="RecipeFermentable.sort_order",
    )
    hops: Mapped[list[RecipeHop]] = relationship(
        back_populates="recipe",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="RecipeHop.sort_order",
    )
    yeasts: Mapped[list[RecipeYeast]] = relationship(
        back_populates="recipe",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="RecipeYeast.sort_order",
    )


def _child_args(*extra: CheckConstraint) -> tuple[object, ...]:
    return (
        ForeignKeyConstraint(
            ["recipe_id", "user_id"], ["recipes.id", "recipes.user_id"], ondelete="CASCADE"
        ),
        CheckConstraint(f"char_length(name) BETWEEN 1 AND {MAX_NAME}", name="name_length"),
        CheckConstraint("sort_order >= 0", name="sort_order"),
        *extra,
    )


class RecipeChild:
    recipe_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    name: Mapped[str] = mapped_column(String(MAX_NAME), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class RecipeFermentable(UUIDv7PrimaryKey, RecipeChild, Base):
    __tablename__ = "recipe_fermentables"
    __table_args__ = _child_args(
        CheckConstraint("type IN ('grain', 'extract', 'sugar', 'adjunct')", name="type"),
        CheckConstraint("addition IN ('mash', 'steep', 'boil', 'fermenter')", name="addition"),
        CheckConstraint("amount_kg > 0 AND amount_kg <= 1000", name="amount"),
        CheckConstraint("ppg >= 0 AND ppg <= 50", name="ppg"),
        CheckConstraint("color_lovibond >= 0 AND color_lovibond <= 700", name="color"),
    )

    fermentable_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("fermentables.id", ondelete="SET NULL")
    )
    type: Mapped[str] = mapped_column(String(16), nullable=False)
    addition: Mapped[str] = mapped_column(String(16), nullable=False)
    amount_kg: Mapped[float] = mapped_column(Double, nullable=False)
    ppg: Mapped[float] = mapped_column(Double, nullable=False)
    color_lovibond: Mapped[float] = mapped_column(Double, nullable=False)

    recipe: Mapped[Recipe] = relationship(back_populates="fermentables")


class RecipeHop(UUIDv7PrimaryKey, RecipeChild, Base):
    __tablename__ = "recipe_hops"
    __table_args__ = _child_args(
        CheckConstraint("use IN ('boil', 'first_wort', 'whirlpool', 'dry_hop')", name="use"),
        CheckConstraint("amount_g > 0 AND amount_g <= 10000", name="amount"),
        CheckConstraint("alpha_pct >= 0 AND alpha_pct <= 25", name="alpha"),
        CheckConstraint("time_min IS NULL OR (time_min >= 0 AND time_min <= 360)", name="time"),
        CheckConstraint(
            "dry_hop_days IS NULL OR (dry_hop_days >= 0 AND dry_hop_days <= 30)",
            name="dry_hop_days",
        ),
        # time_min for boil and whirlpool, dry_hop_days for dry hops, neither for first wort.
        CheckConstraint(
            "(use IN ('boil', 'whirlpool') AND time_min IS NOT NULL AND dry_hop_days IS NULL) "
            "OR (use = 'dry_hop' AND dry_hop_days IS NOT NULL AND time_min IS NULL) "
            "OR (use = 'first_wort' AND time_min IS NULL AND dry_hop_days IS NULL)",
            name="fields_match_use",
        ),
    )

    hop_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("hops.id", ondelete="SET NULL")
    )
    amount_g: Mapped[float] = mapped_column(Double, nullable=False)
    alpha_pct: Mapped[float] = mapped_column(Double, nullable=False)
    use: Mapped[str] = mapped_column(String(16), nullable=False)
    time_min: Mapped[float | None] = mapped_column(Double)
    dry_hop_days: Mapped[float | None] = mapped_column(Double)

    recipe: Mapped[Recipe] = relationship(back_populates="hops")


class RecipeYeast(UUIDv7PrimaryKey, RecipeChild, Base):
    __tablename__ = "recipe_yeasts"
    __table_args__ = _child_args(
        CheckConstraint("attenuation_pct >= 40 AND attenuation_pct <= 100", name="attenuation"),
    )

    yeast_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("yeasts.id", ondelete="SET NULL")
    )
    attenuation_pct: Mapped[float] = mapped_column(Double, nullable=False)

    recipe: Mapped[Recipe] = relationship(back_populates="yeasts")
