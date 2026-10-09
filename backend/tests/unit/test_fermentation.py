"""Apparent attenuation and current ABV against Appendix A, plus the precedence rules."""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.domain import brewmath as bm
from app.domain.fermentation import (
    GravitySource,
    apparent_attenuation,
    current_abv,
    progress,
)
from tests.fixtures import appendix_a_recipe

APPENDIX_A = bm.calculate(appendix_a_recipe())


def test_appendix_a_finished_batch_matches_the_recipe_calculator() -> None:
    """A reading at the predicted FG gives the yeast's attenuation and the recipe's ABV."""
    assert apparent_attenuation(APPENDIX_A.og, APPENDIX_A.fg) == pytest.approx(75.0, abs=1e-9)
    assert current_abv(APPENDIX_A.og, APPENDIX_A.fg) == pytest.approx(5.43, abs=0.01)


def test_halfway_reading() -> None:
    # OG 1.060, reading 1.030: half the extract has gone.
    assert apparent_attenuation(1.060, 1.030) == pytest.approx(50.0)
    assert current_abv(1.060, 1.030) == pytest.approx(0.030 * bm.ABV_FACTOR)


def test_reading_above_og_is_zero_not_negative() -> None:
    assert apparent_attenuation(1.050, 1.055) == 0.0
    assert current_abv(1.050, 1.055) == 0.0


def test_attenuation_needs_an_og_above_water() -> None:
    with pytest.raises(ValueError, match=r"exceed 1\.000"):
        apparent_attenuation(1.000, 1.000)


def test_progress_prefers_measured_values() -> None:
    result = progress(
        measured_og=1.058,
        expected_og=APPENDIX_A.og,
        expected_fg=APPENDIX_A.fg,
        measured_fg=1.012,
        latest_reading_sg=1.020,  # stale device reading, must lose to measured_fg
    )
    assert (result.og, result.og_source) == (1.058, GravitySource.MEASURED)
    assert (result.current_sg, result.current_sg_source) == (1.012, GravitySource.MEASURED)
    assert result.apparent_attenuation_pct == pytest.approx((0.058 - 0.012) / 0.058 * 100)
    assert result.abv == pytest.approx(0.046 * bm.ABV_FACTOR)
    assert result.expected_fg == APPENDIX_A.fg
    # Expected attenuation is relative to the OG in use, so it moves with measured_og.
    assert result.expected_attenuation_pct == pytest.approx((1.058 - APPENDIX_A.fg) / 0.058 * 100)


def test_progress_falls_back_to_estimates_and_readings() -> None:
    result = progress(
        measured_og=None,
        expected_og=APPENDIX_A.og,
        expected_fg=APPENDIX_A.fg,
        measured_fg=None,
        latest_reading_sg=1.030,
    )
    assert (result.og, result.og_source) == (APPENDIX_A.og, GravitySource.ESTIMATED)
    assert (result.current_sg, result.current_sg_source) == (1.030, GravitySource.READING)
    assert result.expected_attenuation_pct == pytest.approx(75.0)
    assert result.apparent_attenuation_pct is not None
    assert 0 < result.apparent_attenuation_pct < 75


def test_progress_without_any_gravity_yet() -> None:
    result = progress(
        measured_og=None,
        expected_og=1.050,
        expected_fg=1.012,
        measured_fg=None,
        latest_reading_sg=None,
    )
    assert result.current_sg is None
    assert result.current_sg_source is None
    assert result.apparent_attenuation_pct is None
    assert result.abv is None
    assert result.expected_attenuation_pct == pytest.approx(76.0)


def test_progress_for_a_recipe_with_no_extract() -> None:
    """OG 1.000 (no fermentables): attenuation is undefined, nothing divides by zero."""
    result = progress(
        measured_og=None,
        expected_og=1.0,
        expected_fg=1.0,
        measured_fg=None,
        latest_reading_sg=1.0,
    )
    assert result.apparent_attenuation_pct is None
    assert result.abv is None
    assert result.expected_attenuation_pct is None


gravities = st.floats(min_value=0.980, max_value=1.200, allow_nan=False, allow_infinity=False)


@given(og=gravities.filter(lambda g: g > 1.0005), sg=gravities)
def test_attenuation_and_abv_are_finite_and_non_negative(og: float, sg: float) -> None:
    attenuation = apparent_attenuation(og, sg)
    alcohol = current_abv(og, sg)
    assert attenuation >= 0 and alcohol >= 0
    if sg <= og:
        # Monotone: the further the gravity has dropped, the more has fermented.
        assert attenuation == pytest.approx((og - sg) / (og - 1) * 100)
        assert alcohol == pytest.approx((og - sg) * bm.ABV_FACTOR)
