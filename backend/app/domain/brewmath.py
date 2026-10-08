"""Recipe statistics: gravity, alcohol, bitterness and colour (plan, Section 7).

Definitions
- Batch volume is the volume of wort into the fermenter; v1 treats post-boil volume as equal
  to it (kettle and trub losses are not modelled).
- Pre-boil volume is optional and only estimates boil gravity for IBU.
- Brewhouse efficiency is the share of a mashed ingredient's potential extract that ends up
  in the batch volume. Steeped grains use the steep efficiency; extracts and sugars count
  fully.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

from app.domain.units import g_to_oz, kg_to_lb, l_to_gal, srm_to_ebc


class Addition(StrEnum):
    MASH = "mash"
    STEEP = "steep"
    BOIL = "boil"
    FERMENTER = "fermenter"


class HopUse(StrEnum):
    BOIL = "boil"
    FIRST_WORT = "first_wort"
    WHIRLPOOL = "whirlpool"
    DRY_HOP = "dry_hop"


class BoilGravityMode(StrEnum):
    OG = "og"
    AVERAGE = "average_of_pre_boil_and_og"


# Yeast attenuation assumed when a recipe has no yeast (reported as assumed).
DEFAULT_ATTENUATION_PCT = 75.0
# Specialty grains steeped without a mash give up far less of their potential than mashed
# grain; half is a common planning figure and the recipe can override it.
DEFAULT_STEEP_EFFICIENCY_PCT = 50.0
DEFAULT_BREWHOUSE_EFFICIENCY_PCT = 72.0
# Individually valid inputs can combine into nonsense (a tonne of malt in half a litre).
MAX_OG = 1.200
# Above this OG the simple ABV formula drifts; the alternate formula is reported as well.
ALTERNATE_ABV_ABOVE_OG = 1.070
# First wort hops are treated as a full-boil addition plus ten percent.
FIRST_WORT_BONUS = 1.10
# Whirlpool utilisation has no consensus formula: Tinseth for the stand time, scaled down.
DEFAULT_WHIRLPOOL_FACTOR = 0.5

ABV_FACTOR = 131.25
TINSETH_BIGNESS_SCALE = 1.65
TINSETH_BIGNESS_BASE = 0.000125
TINSETH_RATE = 0.04
TINSETH_MAX_UTILISATION_DIVISOR = 4.15
IBU_CONSTANT = 7490.0
MOREY_COEFFICIENT = 1.4922
MOREY_EXPONENT = 0.6859


class RecipeOutOfRangeError(ValueError):
    """The recipe is individually valid but combines into something that cannot be computed."""

    def __init__(self, field: str, message: str) -> None:
        super().__init__(message)
        self.field = field
        self.message = message


@dataclass(frozen=True, slots=True)
class Fermentable:
    name: str
    amount_kg: float
    ppg: float
    color_lovibond: float
    addition: Addition


@dataclass(frozen=True, slots=True)
class Hop:
    name: str
    amount_g: float
    alpha_pct: float
    use: HopUse
    time_min: float | None = None
    dry_hop_days: float | None = None


@dataclass(frozen=True, slots=True)
class Yeast:
    name: str
    attenuation_pct: float


@dataclass(frozen=True, slots=True)
class Recipe:
    batch_volume_l: float
    boil_time_min: float
    brewhouse_efficiency_pct: float = DEFAULT_BREWHOUSE_EFFICIENCY_PCT
    steep_efficiency_pct: float = DEFAULT_STEEP_EFFICIENCY_PCT
    pre_boil_volume_l: float | None = None
    fermentables: tuple[Fermentable, ...] = ()
    hops: tuple[Hop, ...] = ()
    yeasts: tuple[Yeast, ...] = ()


@dataclass(frozen=True, slots=True)
class HopContribution:
    name: str
    use: HopUse
    minutes: float
    utilization: float
    ibu: float
    estimated: bool


@dataclass(frozen=True, slots=True)
class RecipeStats:
    gravity_units: float
    og: float
    fg: float
    abv: float
    abv_alternate: float | None
    attenuation_pct: float
    attenuation_assumed: bool
    mcu: float
    srm: float
    ebc: float
    ibu: float
    boil_gravity: float
    boil_gravity_mode: BoilGravityMode
    hop_contributions: tuple[HopContribution, ...]


# -- gravity -------------------------------------------------------------------------------


def extract_factor(addition: Addition, recipe: Recipe) -> float:
    if addition is Addition.MASH:
        return recipe.brewhouse_efficiency_pct / 100
    if addition is Addition.STEEP:
        return recipe.steep_efficiency_pct / 100
    return 1.0


def gravity_units(recipe: Recipe) -> float:
    batch_gal = l_to_gal(recipe.batch_volume_l)
    if batch_gal <= 0:
        raise RecipeOutOfRangeError("batch_volume_l", "Batch volume must be positive.")
    total = sum(
        kg_to_lb(f.amount_kg) * f.ppg * extract_factor(f.addition, recipe)
        for f in recipe.fermentables
    )
    return total / batch_gal


def original_gravity(recipe: Recipe) -> float:
    og = 1 + gravity_units(recipe) / 1000
    if og > MAX_OG:
        raise RecipeOutOfRangeError(
            "fermentables",
            f"These ingredients give an original gravity above {MAX_OG:.3f}, "
            "which is beyond what the formulas can handle.",
        )
    return og


def attenuation(recipe: Recipe) -> tuple[float, bool]:
    """The first yeast's attenuation, or the default flagged as assumed."""
    if recipe.yeasts:
        return recipe.yeasts[0].attenuation_pct, False
    return DEFAULT_ATTENUATION_PCT, True


def final_gravity(og: float, attenuation_pct: float) -> float:
    return 1 + (og - 1) * (1 - attenuation_pct / 100)


def abv(og: float, fg: float) -> float:
    return (og - fg) * ABV_FACTOR


def abv_alternate(og: float, fg: float) -> float:
    """More accurate for strong beers; its pole at OG 1.775 is far beyond MAX_OG."""
    return 76.08 * (og - fg) / (1.775 - og) * fg / 0.794


# -- bitterness ----------------------------------------------------------------------------


def boil_gravity(recipe: Recipe, og: float) -> tuple[float, BoilGravityMode]:
    """Gravity used for hop utilisation. With a pre-boil volume this is the average of the
    pre-boil gravity and OG, following Tinseth's guidance to use the gravity during the boil."""
    if recipe.pre_boil_volume_l is None:
        return og, BoilGravityMode.OG
    if recipe.pre_boil_volume_l <= 0:
        raise RecipeOutOfRangeError("pre_boil_volume_l", "Pre-boil volume must be positive.")
    pre_boil = 1 + (og - 1) * recipe.batch_volume_l / recipe.pre_boil_volume_l
    return (pre_boil + og) / 2, BoilGravityMode.AVERAGE


def tinseth_utilization(gravity: float, minutes: float) -> float:
    bigness: float = TINSETH_BIGNESS_SCALE * TINSETH_BIGNESS_BASE ** (gravity - 1)
    time_factor = (1 - math.exp(-TINSETH_RATE * minutes)) / TINSETH_MAX_UTILISATION_DIVISOR
    return bigness * time_factor


def hop_contribution(
    hop: Hop, recipe: Recipe, gravity: float, *, whirlpool_factor: float
) -> HopContribution:
    batch_gal = l_to_gal(recipe.batch_volume_l)
    estimated = False
    if hop.use is HopUse.DRY_HOP:
        return HopContribution(hop.name, hop.use, 0.0, 0.0, 0.0, False)
    if hop.use is HopUse.FIRST_WORT:
        minutes = recipe.boil_time_min
        utilization = tinseth_utilization(gravity, minutes) * FIRST_WORT_BONUS
    else:
        if hop.time_min is None:
            raise RecipeOutOfRangeError("hops", f"{hop.name}: {hop.use.value} hops need a time.")
        minutes = hop.time_min
        utilization = tinseth_utilization(gravity, minutes)
        if hop.use is HopUse.WHIRLPOOL:
            utilization *= whirlpool_factor
            estimated = True
    ibu = utilization * (hop.alpha_pct / 100) * g_to_oz(hop.amount_g) * IBU_CONSTANT / batch_gal
    return HopContribution(hop.name, hop.use, minutes, utilization, ibu, estimated)


# -- colour --------------------------------------------------------------------------------


def malt_color_units(recipe: Recipe) -> float:
    batch_gal = l_to_gal(recipe.batch_volume_l)
    return sum(kg_to_lb(f.amount_kg) * f.color_lovibond for f in recipe.fermentables) / batch_gal


def morey_srm(mcu: float) -> float:
    if mcu <= 0:
        return 0.0
    srm: float = MOREY_COEFFICIENT * mcu**MOREY_EXPONENT
    return srm


# -- everything ----------------------------------------------------------------------------


def calculate(recipe: Recipe, *, whirlpool_factor: float = DEFAULT_WHIRLPOOL_FACTOR) -> RecipeStats:
    gu = gravity_units(recipe)
    og = original_gravity(recipe)
    att, assumed = attenuation(recipe)
    fg = final_gravity(og, att)
    gravity, mode = boil_gravity(recipe, og)
    contributions = tuple(
        hop_contribution(h, recipe, gravity, whirlpool_factor=whirlpool_factor) for h in recipe.hops
    )
    mcu = malt_color_units(recipe)
    srm = morey_srm(mcu)
    return RecipeStats(
        gravity_units=gu,
        og=og,
        fg=fg,
        abv=abv(og, fg),
        abv_alternate=abv_alternate(og, fg) if og > ALTERNATE_ABV_ABOVE_OG else None,
        attenuation_pct=att,
        attenuation_assumed=assumed,
        mcu=mcu,
        srm=srm,
        ebc=srm_to_ebc(srm),
        ibu=sum(c.ibu for c in contributions),
        boil_gravity=gravity,
        boil_gravity_mode=mode,
        hop_contributions=contributions,
    )
