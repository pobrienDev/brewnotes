"""The recipe frozen into a batch at brew time.

Stored as JSONB with a schema_version so batches written by older versions of the app stay
readable: `parse_snapshot` dispatches on the version and upgrades older shapes to the current
model. Everything the calculator needs is inside, so a batch can show its expected numbers
after the recipe was edited or deleted.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import Field

from app.domain import brewmath as bm
from app.models import Recipe
from app.models.recipe import MAX_NAME
from app.schemas.base import Schema
from app.schemas.recipe import RecipeInput
from app.schemas.recipes import RecipeFermentableInput, RecipeHopInput, RecipeYeastInput

CURRENT_SNAPSHOT_VERSION = 1


class RecipeSnapshotV1(Schema):
    schema_version: Literal[1] = 1
    recipe_id: uuid.UUID | None = Field(
        description="The recipe this was taken from; it may since have been deleted"
    )
    name: str = Field(min_length=1, max_length=MAX_NAME)
    target_style: str | None = Field(description="Style slug at brew time")
    target_style_name: str | None = Field(description="Style display name at brew time")
    batch_volume_l: float
    pre_boil_volume_l: float | None
    boil_time_min: float
    brewhouse_efficiency_pct: float
    steep_efficiency_pct: float
    fermentables: list[RecipeFermentableInput]
    hops: list[RecipeHopInput]
    yeasts: list[RecipeYeastInput]
    taken_at: datetime

    @classmethod
    def from_recipe(cls, recipe: Recipe, *, taken_at: datetime) -> RecipeSnapshotV1:
        style = recipe.target_style
        return cls(
            recipe_id=recipe.id,
            name=recipe.name,
            target_style=style.slug if style else None,
            target_style_name=style.display_name if style else None,
            batch_volume_l=recipe.batch_volume_l,
            pre_boil_volume_l=recipe.pre_boil_volume_l,
            boil_time_min=recipe.boil_time_min,
            brewhouse_efficiency_pct=recipe.brewhouse_efficiency_pct,
            steep_efficiency_pct=recipe.steep_efficiency_pct,
            fermentables=[RecipeFermentableInput.model_validate(f) for f in recipe.fermentables],
            hops=[RecipeHopInput.model_validate(h) for h in recipe.hops],
            yeasts=[RecipeYeastInput.model_validate(y) for y in recipe.yeasts],
            taken_at=taken_at,
        )

    def to_domain(self) -> bm.Recipe:
        return RecipeInput(
            batch_volume_l=self.batch_volume_l,
            pre_boil_volume_l=self.pre_boil_volume_l,
            boil_time_min=self.boil_time_min,
            brewhouse_efficiency_pct=self.brewhouse_efficiency_pct,
            steep_efficiency_pct=self.steep_efficiency_pct,
            fermentables=self.fermentables,
            hops=self.hops,
            yeasts=self.yeasts,
            target_style=self.target_style,
        ).to_domain()

    def to_json(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


RecipeSnapshot = RecipeSnapshotV1


def parse_snapshot(data: dict[str, Any]) -> RecipeSnapshot:
    """Read a stored snapshot of any supported version as the current model."""
    version = data.get("schema_version")
    if version == 1:
        return RecipeSnapshotV1.model_validate(data)
    raise ValueError(f"unsupported recipe snapshot schema_version {version!r}")
