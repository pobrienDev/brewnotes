from __future__ import annotations

import math

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.domain.style_match import (
    METRICS,
    Metric,
    Range,
    StyleSpec,
    match_metric,
    match_style,
    rank_styles,
)

APA = StyleSpec(
    "american-pale-ale",
    "18B",
    "18B American Pale Ale",
    {
        "og": (Range(1.045, 1.060),),
        "fg": (Range(1.010, 1.015),),
        "abv": (Range(4.5, 6.2),),
        "ibu": (Range(30, 50),),
        "srm": (Range(5, 10),),
    },
)
IPA = StyleSpec(
    "american-ipa",
    "21A",
    "21A American IPA",
    {
        "og": (Range(1.056, 1.070),),
        "fg": (Range(1.008, 1.014),),
        "abv": (Range(5.5, 7.5),),
        "ibu": (Range(40, 70),),
        "srm": (Range(6, 14),),
    },
)
SAISON = StyleSpec(
    "saison",
    "25B",
    "25B Saison",
    {
        "og": (Range(1.048, 1.065, "standard"),),
        "fg": (Range(1.002, 1.008, "standard"),),
        "abv": (Range(3.5, 5.0, "table"), Range(5.0, 7.0, "standard"), Range(7.0, 9.5, "super")),
        "ibu": (Range(20, 35),),
        "srm": (Range(5, 14, "pale"), Range(15, 22, "dark")),
    },
)
BLACK_IPA = StyleSpec(
    "black-ipa",
    "21B",
    "21B Specialty IPA: Black IPA",
    {
        "og": (Range(1.050, 1.085),),
        "fg": (Range(1.010, 1.018),),
        "abv": (Range(5.5, 9.0),),
        "ibu": (Range(50, 90),),
        "srm": (Range(25, 40),),
    },
)
NO_RANGES = StyleSpec("specialty", "34C", "34C Experimental Beer", {})
APPENDIX_A = {"og": 1.055, "fg": 1.014, "abv": 5.43, "ibu": 32.5, "srm": 8.1}


def test_appendix_a_fits_american_pale_ale_first() -> None:
    ranked = rank_styles(APPENDIX_A, [IPA, SAISON, APA, BLACK_IPA, NO_RANGES])
    assert ranked[0].slug == "american-pale-ale"
    assert ranked[0].fits is True
    assert ranked[0].score == 0
    assert all(m.status == "in" for m in ranked[0].metrics)
    # A style with no ranges at all is never matched.
    assert "specialty" not in {m.slug for m in ranked}


def test_misses_are_explained_per_metric() -> None:
    match = match_style(IPA, APPENDIX_A)
    assert match is not None
    assert match.fits is False
    by_metric = {m.metric: m for m in match.metrics}
    assert by_metric["og"].status == "low"
    assert by_metric["og"].delta == pytest.approx(-0.001)
    assert by_metric["ibu"].status == "low"
    assert by_metric["ibu"].delta == pytest.approx(-7.5)
    assert by_metric["srm"].status == "in"
    assert by_metric["fg"].status == "in"  # 1.014 is on the edge: inclusive
    assert match.score == pytest.approx(0.001 / 0.014 + (5.5 - 5.43) / 2.0 + 7.5 / 30)


def test_multi_range_metrics_match_any_range() -> None:
    table = match_style(SAISON, {"abv": 4.0, "srm": 20})
    assert table is not None and table.fits
    between = match_style(SAISON, {"srm": 14.3})
    assert between is not None
    (srm,) = between.metrics
    assert srm.status == "high"  # nearest range is pale (5-14); 14.3 is just above it
    assert srm.delta == pytest.approx(0.3)
    assert srm.penalty == pytest.approx(0.3 / 9)
    dark_side = match_style(SAISON, {"srm": 14.8})
    assert dark_side is not None
    assert dark_side.metrics[0].status == "low"  # nearer to dark (15-22)


def test_boundaries_are_inclusive() -> None:
    assert match_metric("ibu", 30, (Range(30, 50),)).status == "in"
    assert match_metric("ibu", 50, (Range(30, 50),)).status == "in"
    assert match_metric("ibu", 50.0001, (Range(30, 50),)).status == "high"


def test_width_floor_prevents_division_by_zero() -> None:
    result = match_metric("og", 1.060, (Range(1.050, 1.050),))
    assert result.penalty == pytest.approx(0.010 / 0.002)
    assert math.isfinite(result.penalty)


def test_ranking_prefers_fits_then_more_metrics_then_lower_score() -> None:
    partial = StyleSpec("partial", None, "Partial", {"og": (Range(1.050, 1.060),)})
    near_miss = StyleSpec(
        "near",
        None,
        "Near",
        {m: (Range(0, 0.5),) if m == "srm" else r for m, r in APA.ranges.items()},
    )
    ranked = rank_styles(APPENDIX_A, [near_miss, partial, APA])
    assert [m.slug for m in ranked] == ["american-pale-ale", "partial", "near"]


def test_target_style_is_appended_when_it_misses_the_cut() -> None:
    styles = [APA, IPA, SAISON, BLACK_IPA] + [
        StyleSpec(f"clone-{i}", None, f"Clone {i}", APA.ranges) for i in range(6)
    ]
    ranked = rank_styles(APPENDIX_A, styles, target_slug="black-ipa")
    assert len(ranked) == 6
    assert ranked[-1].slug == "black-ipa"
    assert ranked[-1].fits is False
    ranked_with_fitting_target = rank_styles(APPENDIX_A, styles, target_slug="american-pale-ale")
    assert len(ranked_with_fitting_target) == 5


def test_weights_change_the_score_only() -> None:
    plain = match_style(IPA, APPENDIX_A)
    weighted = match_style(IPA, APPENDIX_A, weights={"ibu": 10})
    assert plain is not None and weighted is not None
    assert weighted.score > plain.score
    assert weighted.fits == plain.fits


@st.composite
def ranges(draw: st.DrawFn) -> tuple[Range, ...]:
    lows = draw(st.lists(st.floats(0, 100, allow_nan=False), min_size=1, max_size=3))
    return tuple(Range(low, low + draw(st.floats(0, 10, allow_nan=False))) for low in lows)


@settings(max_examples=300)
@given(
    value=st.floats(-10, 200, allow_nan=False),
    metric=st.sampled_from(METRICS),
    rs=ranges(),
)
def test_matching_never_divides_by_zero_or_produces_nan(
    value: float, metric: Metric, rs: tuple[Range, ...]
) -> None:
    result = match_metric(metric, value, rs)
    assert math.isfinite(result.penalty)
    assert math.isfinite(result.delta)
    assert result.penalty >= 0
    if result.status == "in":
        assert result.penalty == 0 and result.delta == 0
    else:
        assert result.delta != 0
