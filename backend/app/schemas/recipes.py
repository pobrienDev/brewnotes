"""Saved recipes: the calculator's recipe body plus a name, notes and catalog references."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime
from typing import Literal

from pydantic import Field

from app.models.recipe import MAX_NAME, MAX_NOTES
from app.schemas.base import Schema
from app.schemas.calc import RecipeStatsOut, StyleMatchOut
from app.schemas.recipe import FermentableInput, HopInput, RecipeInput, YeastInput
from app.schemas.styles import StyleSummary

FermentableType = Literal["grain", "extract", "sugar", "adjunct"]


class RecipeFermentableInput(FermentableInput):
    type: FermentableType
    fermentable_id: uuid.UUID | None = Field(
        default=None, description="Catalog row this was taken from; values are snapshots"
    )


class RecipeHopInput(HopInput):
    hop_id: uuid.UUID | None = None


class RecipeYeastInput(YeastInput):
    yeast_id: uuid.UUID | None = None


class RecipeWrite(RecipeInput):
    """Body for creating or replacing a recipe."""

    name: str = Field(min_length=1, max_length=MAX_NAME)
    notes: str = Field(default="", max_length=MAX_NOTES)
    fermentables: Sequence[RecipeFermentableInput] = Field(default_factory=list, max_length=50)
    hops: Sequence[RecipeHopInput] = Field(default_factory=list, max_length=50)
    yeasts: Sequence[RecipeYeastInput] = Field(default_factory=list, max_length=50)


class RecipeFermentableOut(RecipeFermentableInput):
    id: uuid.UUID


class RecipeHopOut(RecipeHopInput):
    id: uuid.UUID


class RecipeYeastOut(RecipeYeastInput):
    id: uuid.UUID


class RecipeOut(Schema):
    id: uuid.UUID
    name: str
    notes: str
    target_style: StyleSummary | None
    batch_volume_l: float
    pre_boil_volume_l: float | None
    boil_time_min: float
    brewhouse_efficiency_pct: float
    steep_efficiency_pct: float
    fermentables: list[RecipeFermentableOut]
    hops: list[RecipeHopOut]
    yeasts: list[RecipeYeastOut]
    created_at: datetime
    updated_at: datetime
    stats: RecipeStatsOut
    style_matches: list[StyleMatchOut]
    calc_notes: list[str]


class RecipeSummary(Schema):
    id: uuid.UUID
    name: str
    target_style: StyleSummary | None
    og: float
    fg: float
    abv: float
    ibu: float
    srm: float
    updated_at: datetime
