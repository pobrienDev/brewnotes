from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.domain import brewmath as bm
from app.domain.brewmath import Addition, Fermentable, Hop, HopUse, Recipe, Yeast
from app.domain.scaling import scale_to_efficiency, scale_to_volume
from app.domain.units import gal_to_l, kg_to_lb, l_to_gal, oz_to_g
from tests.fixtures import appendix_a_recipe


def test_appendix_a_scaled_to_ten_gallons() -> None:
    scaled = scale_to_volume(appendix_a_recipe(pre_boil=True), gal_to_l(10))
    assert [round(kg_to_lb(f.amount_kg), 2) for f in scaled.fermentables] == [18.18, 0.91, 1.82]
    assert all(round(h.amount_g / oz_to_g(1), 2) == 1.82 for h in scaled.hops)
    assert l_to_gal(scaled.pre_boil_volume_l or 0) == pytest.approx(11.82, abs=0.005)
    assert scaled.boil_time_min == 60
    assert scaled.yeasts == appendix_a_recipe().yeasts

    before = bm.calculate(appendix_a_recipe(pre_boil=True))
    after = bm.calculate(scaled)
    for metric in ("og", "fg", "abv", "ibu", "srm"):
        assert getattr(after, metric) == pytest.approx(getattr(before, metric), rel=1e-9)


def test_efficiency_scaling_keeps_og_and_only_touches_mash_additions() -> None:
    recipe = Recipe(
        gal_to_l(5),
        60,
        brewhouse_efficiency_pct=72,
        fermentables=(
            Fermentable("pale", 4, 37, 2, Addition.MASH),
            Fermentable("sugar", 0.5, 46, 0, Addition.BOIL),
            Fermentable("crystal", 0.3, 34, 60, Addition.STEEP),
        ),
    )
    scaled = scale_to_efficiency(recipe, 80)
    assert scaled.brewhouse_efficiency_pct == 80
    assert scaled.fermentables[0].amount_kg == pytest.approx(4 * 72 / 80)
    assert scaled.fermentables[1].amount_kg == 0.5
    assert scaled.fermentables[2].amount_kg == 0.3
    assert bm.calculate(scaled).og == pytest.approx(bm.calculate(recipe).og, rel=1e-12)


def test_invalid_targets_are_rejected() -> None:
    with pytest.raises(ValueError, match="positive"):
        scale_to_volume(appendix_a_recipe(), 0)
    with pytest.raises(ValueError, match="positive"):
        scale_to_efficiency(appendix_a_recipe(), 0)


# -- property tests --------------------------------------------------------------------------

positive = st.floats(min_value=0.01, max_value=1_000, allow_nan=False, allow_infinity=False)
volumes = st.floats(min_value=0.5, max_value=2_000, allow_nan=False, allow_infinity=False)
efficiencies = st.floats(min_value=20, max_value=100, allow_nan=False, allow_infinity=False)


@st.composite
def recipes(draw: st.DrawFn) -> Recipe:
    batch = draw(volumes)
    pre_boil = draw(st.one_of(st.none(), st.floats(min_value=batch, max_value=2_500)))
    fermentables = tuple(
        Fermentable(
            f"f{i}",
            draw(st.floats(min_value=0.001, max_value=5)),
            draw(st.floats(min_value=0, max_value=50)),
            draw(st.floats(min_value=0, max_value=700)),
            draw(st.sampled_from(list(Addition))),
        )
        for i in range(draw(st.integers(0, 4)))
    )
    hops = tuple(
        Hop(
            f"h{i}",
            draw(st.floats(min_value=0.1, max_value=500)),
            draw(st.floats(min_value=0, max_value=25)),
            HopUse.BOIL,
            time_min=draw(st.floats(min_value=0, max_value=60)),
        )
        for i in range(draw(st.integers(0, 3)))
    )
    yeasts = tuple(
        Yeast("y", draw(st.floats(min_value=40, max_value=100)))
        for _ in range(draw(st.integers(0, 1)))
    )
    return Recipe(
        batch_volume_l=batch,
        boil_time_min=60,
        brewhouse_efficiency_pct=draw(efficiencies),
        pre_boil_volume_l=pre_boil,
        fermentables=fermentables,
        hops=hops,
        yeasts=yeasts,
    )


@settings(max_examples=200)
@given(recipe=recipes(), new_volume=volumes)
def test_volume_scaling_round_trips(recipe: Recipe, new_volume: float) -> None:
    back = scale_to_volume(scale_to_volume(recipe, new_volume), recipe.batch_volume_l)
    for original, returned in zip(recipe.fermentables, back.fermentables, strict=True):
        assert returned.amount_kg == pytest.approx(original.amount_kg, rel=1e-9)
    for original_hop, returned_hop in zip(recipe.hops, back.hops, strict=True):
        assert returned_hop.amount_g == pytest.approx(original_hop.amount_g, rel=1e-9)
    if recipe.pre_boil_volume_l is None:
        assert back.pre_boil_volume_l is None
    else:
        assert back.pre_boil_volume_l == pytest.approx(recipe.pre_boil_volume_l, rel=1e-9)


@settings(max_examples=200)
@given(recipe=recipes(), new_volume=volumes)
def test_linear_scaling_keeps_every_stat(recipe: Recipe, new_volume: float) -> None:
    try:
        before = bm.calculate(recipe)
    except bm.RecipeOutOfRangeError:
        return  # the generated recipe is nonsense; scaling nonsense is not interesting
    after = bm.calculate(scale_to_volume(recipe, new_volume))
    for metric in ("og", "fg", "abv", "ibu", "srm", "boil_gravity"):
        assert getattr(after, metric) == pytest.approx(getattr(before, metric), rel=1e-9, abs=1e-12)


@settings(max_examples=200)
@given(recipe=recipes(), new_efficiency=efficiencies)
def test_efficiency_scaling_keeps_og(recipe: Recipe, new_efficiency: float) -> None:
    try:
        before = bm.calculate(recipe)
    except bm.RecipeOutOfRangeError:
        return
    after = bm.calculate(scale_to_efficiency(recipe, new_efficiency))
    assert after.og == pytest.approx(before.og, rel=1e-9, abs=1e-12)
