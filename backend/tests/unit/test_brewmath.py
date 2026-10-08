"""Appendix A fixtures, every formula, and the edges of the input space."""

from __future__ import annotations

import pytest

from app.domain import brewmath as bm
from app.domain.brewmath import Addition, Fermentable, Hop, HopUse, Recipe, Yeast
from app.domain.units import gal_to_l, lb_to_kg, oz_to_g
from tests.fixtures import (
    APPENDIX_A_EXPECTED,
    APPENDIX_A_IBU_NO_PRE_BOIL,
    APPENDIX_A_IBU_WITH_PRE_BOIL,
    appendix_a_recipe,
)

# Accuracy targets from the plan, Section 8.
OG_TOL, ABV_TOL, IBU_TOL, SRM_TOL = 0.001, 0.1, 1.0, 0.5


@pytest.mark.parametrize("exact", [True, False], ids=["exact-imperial", "rounded-metric"])
def test_appendix_a_gravity_alcohol_and_colour(exact: bool) -> None:
    stats = bm.calculate(appendix_a_recipe(exact=exact))
    e = APPENDIX_A_EXPECTED
    assert stats.gravity_units == pytest.approx(e.gravity_units, abs=0.05)
    assert stats.og == pytest.approx(e.og, abs=OG_TOL)
    assert stats.fg == pytest.approx(e.fg, abs=OG_TOL)
    assert stats.abv == pytest.approx(e.abv, abs=ABV_TOL)
    assert stats.mcu == pytest.approx(e.mcu, abs=0.05)
    assert stats.srm == pytest.approx(e.srm, abs=SRM_TOL)
    assert stats.ebc == pytest.approx(e.ebc, abs=SRM_TOL * 1.97)
    assert stats.attenuation_pct == 75
    assert stats.attenuation_assumed is False
    assert stats.abv_alternate is None  # OG below 1.070


def test_appendix_a_ibu_without_pre_boil_volume() -> None:
    stats = bm.calculate(appendix_a_recipe(pre_boil=False))
    e = APPENDIX_A_IBU_NO_PRE_BOIL
    assert stats.boil_gravity_mode is bm.BoilGravityMode.OG
    assert stats.boil_gravity == pytest.approx(e.boil_gravity, abs=0.0001)
    for contribution, util, ibu in zip(stats.hop_contributions, e.utilization, e.ibu, strict=True):
        assert contribution.utilization == pytest.approx(util, abs=0.0001)
        assert contribution.ibu == pytest.approx(ibu, abs=0.01)
        assert contribution.estimated is False
    assert stats.ibu == pytest.approx(e.total, abs=IBU_TOL)


def test_appendix_a_ibu_with_pre_boil_volume() -> None:
    recipe = appendix_a_recipe(pre_boil=True)
    stats = bm.calculate(recipe)
    e = APPENDIX_A_IBU_WITH_PRE_BOIL
    assert stats.boil_gravity_mode is bm.BoilGravityMode.AVERAGE
    pre_boil = 1 + (stats.og - 1) * recipe.batch_volume_l / (recipe.pre_boil_volume_l or 1)
    assert pre_boil == pytest.approx(e.pre_boil_gravity, abs=0.0001)
    assert stats.boil_gravity == pytest.approx(e.boil_gravity, abs=0.0001)
    for contribution, util, ibu in zip(stats.hop_contributions, e.utilization, e.ibu, strict=True):
        assert contribution.utilization == pytest.approx(util, abs=0.0001)
        assert contribution.ibu == pytest.approx(ibu, abs=0.01)
    assert stats.ibu == pytest.approx(e.total, abs=IBU_TOL)


# -- gravity -------------------------------------------------------------------------------


def _single(
    fermentable: Fermentable,
    *,
    yeasts: tuple[Yeast, ...] = (),
    brewhouse_efficiency_pct: float = 72,
) -> Recipe:
    return Recipe(
        batch_volume_l=gal_to_l(5),
        boil_time_min=60,
        brewhouse_efficiency_pct=brewhouse_efficiency_pct,
        fermentables=(fermentable,),
        yeasts=yeasts,
    )


def test_extract_factors_by_addition() -> None:
    recipe = Recipe(gal_to_l(5), 60, brewhouse_efficiency_pct=70, steep_efficiency_pct=40)
    assert bm.extract_factor(Addition.MASH, recipe) == 0.7
    assert bm.extract_factor(Addition.STEEP, recipe) == 0.4
    assert bm.extract_factor(Addition.BOIL, recipe) == 1.0
    assert bm.extract_factor(Addition.FERMENTER, recipe) == 1.0


def test_one_pound_of_extract_in_one_gallon_gives_its_ppg() -> None:
    recipe = Recipe(
        gal_to_l(1), 60, fermentables=(Fermentable("DME", lb_to_kg(1), 44, 3, Addition.BOIL),)
    )
    assert bm.gravity_units(recipe) == pytest.approx(44)
    assert bm.original_gravity(recipe) == pytest.approx(1.044)


def test_crystal_malt_in_an_all_grain_mash_uses_brewhouse_efficiency() -> None:
    recipe = _single(Fermentable("Crystal 60", lb_to_kg(1), 34, 60, Addition.MASH))
    assert bm.gravity_units(recipe) == pytest.approx(34 * 0.72 / 5)


def test_steeped_grain_uses_steep_efficiency() -> None:
    recipe = _single(Fermentable("Crystal 60", lb_to_kg(1), 34, 60, Addition.STEEP))
    assert bm.gravity_units(recipe) == pytest.approx(34 * 0.5 / 5)


def test_no_fermentables_means_water() -> None:
    stats = bm.calculate(Recipe(gal_to_l(5), 60))
    assert (stats.og, stats.fg, stats.abv, stats.ibu, stats.srm) == (1.0, 1.0, 0.0, 0.0, 0.0)


def test_absurd_recipe_is_rejected_not_computed() -> None:
    recipe = Recipe(
        batch_volume_l=0.5,
        boil_time_min=60,
        fermentables=(Fermentable("malt", 1000, 37, 2, Addition.MASH),),
    )
    with pytest.raises(bm.RecipeOutOfRangeError) as excinfo:
        bm.calculate(recipe)
    assert excinfo.value.field == "fermentables"


def test_og_exactly_at_the_cap_is_allowed() -> None:
    # 1 gal, PPG 50 extract: 4 lb gives 200 gravity units.
    recipe = Recipe(
        gal_to_l(1), 60, fermentables=(Fermentable("x", lb_to_kg(4), 50, 0, Addition.BOIL),)
    )
    assert bm.original_gravity(recipe) == pytest.approx(1.200)


def test_default_attenuation_is_flagged_as_assumed() -> None:
    recipe = _single(Fermentable("pale", lb_to_kg(10), 37, 2, Addition.MASH))
    stats = bm.calculate(recipe)
    assert stats.attenuation_assumed is True
    assert stats.attenuation_pct == 75


def test_first_yeast_decides_attenuation() -> None:
    recipe = _single(
        Fermentable("pale", lb_to_kg(10), 37, 2, Addition.MASH),
        yeasts=(Yeast("A", 80), Yeast("B", 70)),
    )
    stats = bm.calculate(recipe)
    assert stats.attenuation_pct == 80
    assert stats.fg == pytest.approx(1 + (stats.og - 1) * 0.2)


def test_alternate_abv_reported_for_strong_beers() -> None:
    recipe = _single(
        Fermentable("pale", lb_to_kg(15), 37, 2, Addition.MASH), brewhouse_efficiency_pct=75
    )
    stats = bm.calculate(recipe)
    assert stats.og > 1.070
    assert stats.abv_alternate is not None
    assert stats.abv_alternate == pytest.approx(
        76.08 * (stats.og - stats.fg) / (1.775 - stats.og) * stats.fg / 0.794
    )
    assert stats.abv_alternate > stats.abv


# -- bitterness ----------------------------------------------------------------------------


def _hop_recipe(hop: Hop) -> Recipe:
    return Recipe(
        batch_volume_l=gal_to_l(5),
        boil_time_min=60,
        fermentables=(Fermentable("pale", lb_to_kg(10), 37, 2, Addition.MASH),),
        hops=(hop,),
    )


def test_tinseth_shape() -> None:
    assert bm.tinseth_utilization(1.050, 0) == 0
    assert bm.tinseth_utilization(1.050, 60) > bm.tinseth_utilization(1.050, 30)
    assert bm.tinseth_utilization(1.040, 60) > bm.tinseth_utilization(1.080, 60)
    assert bm.tinseth_utilization(1.000, 1e9) == pytest.approx(1.65 / 4.15)


def test_zero_minute_boil_hop_adds_no_bitterness() -> None:
    stats = bm.calculate(_hop_recipe(Hop("late", oz_to_g(2), 10, HopUse.BOIL, time_min=0)))
    assert stats.ibu == 0


def test_dry_hop_adds_no_bitterness() -> None:
    stats = bm.calculate(_hop_recipe(Hop("dry", oz_to_g(4), 12, HopUse.DRY_HOP, dry_hop_days=3)))
    assert stats.ibu == 0
    assert stats.hop_contributions[0].minutes == 0


def test_first_wort_hop_is_full_boil_plus_ten_percent() -> None:
    boil = bm.calculate(_hop_recipe(Hop("h", oz_to_g(1), 10, HopUse.BOIL, time_min=60)))
    first_wort = bm.calculate(_hop_recipe(Hop("h", oz_to_g(1), 10, HopUse.FIRST_WORT)))
    assert first_wort.ibu == pytest.approx(boil.ibu * 1.10)
    assert first_wort.hop_contributions[0].minutes == 60


def test_whirlpool_is_an_estimate_scaled_by_the_factor() -> None:
    boil = bm.calculate(_hop_recipe(Hop("h", oz_to_g(1), 10, HopUse.BOIL, time_min=20)))
    whirlpool = bm.calculate(_hop_recipe(Hop("h", oz_to_g(1), 10, HopUse.WHIRLPOOL, time_min=20)))
    assert whirlpool.ibu == pytest.approx(boil.ibu * 0.5)
    assert whirlpool.hop_contributions[0].estimated is True
    custom = bm.calculate(
        _hop_recipe(Hop("h", oz_to_g(1), 10, HopUse.WHIRLPOOL, time_min=20)), whirlpool_factor=0.3
    )
    assert custom.ibu == pytest.approx(boil.ibu * 0.3)


def test_boil_hop_without_time_is_an_error() -> None:
    with pytest.raises(bm.RecipeOutOfRangeError) as excinfo:
        bm.calculate(_hop_recipe(Hop("h", oz_to_g(1), 10, HopUse.BOIL)))
    assert excinfo.value.field == "hops"


def test_ibu_scales_linearly_with_amount_and_alpha() -> None:
    base = bm.calculate(_hop_recipe(Hop("h", oz_to_g(1), 5, HopUse.BOIL, time_min=30))).ibu
    double_amount = bm.calculate(_hop_recipe(Hop("h", oz_to_g(2), 5, HopUse.BOIL, time_min=30))).ibu
    double_alpha = bm.calculate(_hop_recipe(Hop("h", oz_to_g(1), 10, HopUse.BOIL, time_min=30))).ibu
    assert double_amount == pytest.approx(base * 2)
    assert double_alpha == pytest.approx(base * 2)


# -- colour --------------------------------------------------------------------------------


def test_morey_colour() -> None:
    assert bm.morey_srm(0) == 0
    assert bm.morey_srm(11.727) == pytest.approx(8.08, abs=0.01)
    recipe = _single(Fermentable("black", lb_to_kg(1), 25, 500, Addition.MASH))
    stats = bm.calculate(recipe)
    assert stats.mcu == pytest.approx(100)
    assert stats.srm == pytest.approx(1.4922 * 100**0.6859)
