"""LTTB keeps the shape, the ends, and never more points than asked for."""

from __future__ import annotations

import math

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.domain.downsample import carry_forward, lttb_indices


def test_short_series_is_returned_whole() -> None:
    assert lttb_indices([0, 1, 2], [1, 2, 3], threshold=3) == [0, 1, 2]
    assert lttb_indices([0, 1], [1, 2], threshold=10) == [0, 1]
    assert lttb_indices([], [], threshold=5) == []


def test_two_points_keep_the_ends() -> None:
    xs = list(range(100))
    assert lttb_indices(xs, [0.0] * 100, threshold=2) == [0, 99]


def test_keeps_a_spike_in_a_flat_series() -> None:
    xs = [float(i) for i in range(1000)]
    ys = [1.050] * 1000
    ys[437] = 1.090  # a single outlier must survive heavy downsampling
    kept = lttb_indices(xs, ys, threshold=20)
    assert 437 in kept
    assert kept[0] == 0 and kept[-1] == 999


def test_follows_a_fermentation_curve() -> None:
    """An exponential gravity drop sampled to 12 points stays monotone and close to the curve."""
    xs = [float(h) for h in range(0, 24 * 14, 1)]  # hourly for two weeks
    ys = [1.012 + 0.048 * math.exp(-h / 60) for h in xs]
    kept = lttb_indices(xs, ys, threshold=12)
    assert len(kept) == 12
    sampled = [ys[i] for i in kept]
    assert sampled == sorted(sampled, reverse=True)
    # Early points are dense where the curve bends, sparse along the tail.
    assert kept[1] - kept[0] < kept[-1] - kept[-2]


def test_rejects_bad_arguments() -> None:
    with pytest.raises(ValueError, match="at least 2"):
        lttb_indices([0, 1, 2], [0, 1, 2], threshold=1)
    with pytest.raises(ValueError, match="same length"):
        lttb_indices([0, 1, 2], [0, 1], threshold=2)


@settings(max_examples=200, deadline=None)
@given(
    ys=st.lists(
        st.floats(min_value=0.98, max_value=1.2, allow_nan=False), min_size=0, max_size=400
    ),
    threshold=st.integers(min_value=2, max_value=50),
)
def test_lttb_properties(ys: list[float], threshold: int) -> None:
    xs = [float(i) for i in range(len(ys))]
    kept = lttb_indices(xs, ys, threshold)
    assert len(kept) == min(len(ys), threshold)
    assert kept == sorted(set(kept))  # strictly increasing, no repeats
    if ys:
        assert kept[0] == 0 and kept[-1] == len(ys) - 1


def test_carry_forward() -> None:
    filled = carry_forward([None, None, 1.05, None, 1.04, None])
    assert filled == [1.05, 1.05, 1.05, 1.05, 1.04, 1.04]
    assert carry_forward([None, None]) == [0.0, 0.0]
    assert carry_forward([]) == []
    assert carry_forward([1.0, 2.0]) == [1.0, 2.0]
