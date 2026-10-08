"""Recipe input with every numeric bound from the plan (Section 5)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

from pydantic import Field, model_validator

from app.domain import brewmath as bm
from app.schemas.base import Schema

AdditionName = Literal["mash", "steep", "boil", "fermenter"]
HopUseName = Literal["boil", "first_wort", "whirlpool", "dry_hop"]

MAX_NAME = 200
MAX_INGREDIENTS_PER_TYPE = 50


class FermentableInput(Schema):
    name: str = Field(min_length=1, max_length=MAX_NAME)
    amount_kg: float = Field(gt=0, le=1000)
    ppg: float = Field(ge=0, le=50)
    color_lovibond: float = Field(ge=0, le=700)
    addition: AdditionName

    def to_domain(self) -> bm.Fermentable:
        return bm.Fermentable(
            self.name, self.amount_kg, self.ppg, self.color_lovibond, bm.Addition(self.addition)
        )


class HopInput(Schema):
    name: str = Field(min_length=1, max_length=MAX_NAME)
    amount_g: float = Field(gt=0, le=10_000)
    alpha_pct: float = Field(ge=0, le=25)
    use: HopUseName
    time_min: float | None = Field(default=None, ge=0, le=360)
    dry_hop_days: float | None = Field(default=None, ge=0, le=30)

    @model_validator(mode="after")
    def _fields_match_use(self) -> HopInput:
        if self.use in ("boil", "whirlpool"):
            if self.time_min is None:
                raise ValueError(f"{self.use} hops need time_min")
            if self.dry_hop_days is not None:
                raise ValueError(f"{self.use} hops do not take dry_hop_days")
        elif self.use == "dry_hop":
            if self.dry_hop_days is None:
                raise ValueError("dry_hop hops need dry_hop_days")
            if self.time_min is not None:
                raise ValueError("dry_hop hops do not take time_min")
        elif self.time_min is not None or self.dry_hop_days is not None:
            raise ValueError("first_wort hops use the recipe's boil time; leave both fields empty")
        return self

    def to_domain(self) -> bm.Hop:
        return bm.Hop(
            self.name,
            self.amount_g,
            self.alpha_pct,
            bm.HopUse(self.use),
            time_min=self.time_min,
            dry_hop_days=self.dry_hop_days,
        )


class YeastInput(Schema):
    name: str = Field(min_length=1, max_length=MAX_NAME)
    attenuation_pct: float = Field(ge=40, le=100)

    def to_domain(self) -> bm.Yeast:
        return bm.Yeast(self.name, self.attenuation_pct)


class RecipeInput(Schema):
    batch_volume_l: float = Field(ge=0.5, le=2000, description="Volume into the fermenter")
    pre_boil_volume_l: float | None = Field(
        default=None, le=2500, description="Optional; only used to estimate boil gravity"
    )
    boil_time_min: float = Field(ge=0, le=360)
    brewhouse_efficiency_pct: float = Field(
        default=bm.DEFAULT_BREWHOUSE_EFFICIENCY_PCT, ge=20, le=100
    )
    steep_efficiency_pct: float = Field(default=bm.DEFAULT_STEEP_EFFICIENCY_PCT, ge=20, le=100)
    fermentables: Sequence[FermentableInput] = Field(
        default_factory=list, max_length=MAX_INGREDIENTS_PER_TYPE
    )
    hops: Sequence[HopInput] = Field(default_factory=list, max_length=MAX_INGREDIENTS_PER_TYPE)
    yeasts: Sequence[YeastInput] = Field(default_factory=list, max_length=MAX_INGREDIENTS_PER_TYPE)
    target_style: str | None = Field(
        default=None, max_length=120, description="Slug of the style the recipe aims for"
    )

    @model_validator(mode="after")
    def _cross_field_rules(self) -> RecipeInput:
        if self.pre_boil_volume_l is not None and self.pre_boil_volume_l < self.batch_volume_l:
            raise ValueError("pre_boil_volume_l must be at least the batch volume")
        for index, hop in enumerate(self.hops):
            if hop.use == "boil" and hop.time_min is not None and hop.time_min > self.boil_time_min:
                raise ValueError(f"hops[{index}]: a boil hop's time cannot exceed the boil time")
        return self

    def to_domain(self) -> bm.Recipe:
        return bm.Recipe(
            batch_volume_l=self.batch_volume_l,
            boil_time_min=self.boil_time_min,
            brewhouse_efficiency_pct=self.brewhouse_efficiency_pct,
            steep_efficiency_pct=self.steep_efficiency_pct,
            pre_boil_volume_l=self.pre_boil_volume_l,
            fermentables=tuple(f.to_domain() for f in self.fermentables),
            hops=tuple(h.to_domain() for h in self.hops),
            yeasts=tuple(y.to_domain() for y in self.yeasts),
        )

    @classmethod
    def from_domain(cls, recipe: bm.Recipe, *, target_style: str | None) -> RecipeInput:
        return cls(
            batch_volume_l=recipe.batch_volume_l,
            pre_boil_volume_l=recipe.pre_boil_volume_l,
            boil_time_min=recipe.boil_time_min,
            brewhouse_efficiency_pct=recipe.brewhouse_efficiency_pct,
            steep_efficiency_pct=recipe.steep_efficiency_pct,
            fermentables=[
                FermentableInput(
                    name=f.name,
                    amount_kg=f.amount_kg,
                    ppg=f.ppg,
                    color_lovibond=f.color_lovibond,
                    addition=f.addition.value,
                )
                for f in recipe.fermentables
            ],
            hops=[
                HopInput(
                    name=h.name,
                    amount_g=h.amount_g,
                    alpha_pct=h.alpha_pct,
                    use=h.use.value,
                    time_min=h.time_min,
                    dry_hop_days=h.dry_hop_days,
                )
                for h in recipe.hops
            ],
            yeasts=[
                YeastInput(name=y.name, attenuation_pct=y.attenuation_pct) for y in recipe.yeasts
            ],
            target_style=target_style,
        )
