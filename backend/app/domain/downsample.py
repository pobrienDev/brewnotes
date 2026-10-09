"""Downsampling for the fermentation chart.

Largest-Triangle-Three-Buckets (Steinarsson, 2013) keeps the points that matter visually:
peaks, troughs and inflection points survive, flat stretches collapse. It works on indices so
the caller can map the chosen points back to whole readings (gravity and temperature together).
"""

from __future__ import annotations

from collections.abc import Sequence


def carry_forward(values: Sequence[float | None]) -> list[float]:
    """Fill gaps with the previous known value; leading gaps take the first known value.

    An all-None sequence becomes zeros so the caller can still sample evenly over time.
    """
    first_known = next((v for v in values if v is not None), 0.0)
    filled: list[float] = []
    last = first_known
    for value in values:
        if value is not None:
            last = value
        filled.append(last)
    return filled


def lttb_indices(xs: Sequence[float], ys: Sequence[float], threshold: int) -> list[int]:
    """Indices of the points kept when reducing (xs, ys) to at most `threshold` points.

    Requires threshold >= 2 and xs sorted ascending. Always keeps the first and last point;
    returns every index unchanged when the series is already short enough.
    """
    if threshold < 2:
        raise ValueError("threshold must be at least 2")
    if len(xs) != len(ys):
        raise ValueError("xs and ys must have the same length")
    n = len(xs)
    if n <= threshold:
        return list(range(n))
    if threshold == 2:
        return [0, n - 1]

    sampled = [0]
    bucket_size = (n - 2) / (threshold - 2)
    anchor = 0
    for bucket in range(threshold - 2):
        # The next bucket's average point is the third vertex of every candidate triangle.
        avg_start = int((bucket + 1) * bucket_size) + 1
        avg_end = min(int((bucket + 2) * bucket_size) + 1, n)
        avg_count = avg_end - avg_start
        avg_x = sum(xs[avg_start:avg_end]) / avg_count
        avg_y = sum(ys[avg_start:avg_end]) / avg_count

        start = int(bucket * bucket_size) + 1
        end = int((bucket + 1) * bucket_size) + 1
        ax, ay = xs[anchor], ys[anchor]
        best, best_area = start, -1.0
        for j in range(start, end):
            area = abs((ax - avg_x) * (ys[j] - ay) - (ax - xs[j]) * (avg_y - ay))
            if area > best_area:
                best, best_area = j, area
        sampled.append(best)
        anchor = best
    sampled.append(n - 1)
    return sampled
