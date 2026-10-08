"""Rank BJCP styles by how well a recipe's statistics fit, and explain every miss (Section 8).

Styles may carry several ranges for one metric (Saison's table/standard/super ABV, pale/dark
SRM), and variants such as Black IPA are matched as styles in their own right.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Literal

Metric = Literal["og", "fg", "abv", "ibu", "srm"]
METRICS: tuple[Metric, ...] = ("og", "fg", "abv", "ibu", "srm")
Status = Literal["in", "low", "high"]

# A range narrower than this is widened for the penalty calculation, so a near miss on a
# very tight range is not punished out of proportion and nothing divides by zero.
WIDTH_FLOOR: dict[str, float] = {"og": 0.002, "fg": 0.002, "abv": 0.2, "ibu": 2.0, "srm": 1.0}
DEFAULT_LIMIT = 5


@dataclass(frozen=True, slots=True)
class Range:
    min: float
    max: float
    label: str | None = None

    def width(self, metric: str) -> float:
        return max(self.max - self.min, WIDTH_FLOOR[metric])

    def midpoint(self) -> float:
        return (self.min + self.max) / 2

    def distance(self, value: float) -> float:
        """0 inside (inclusive), else the distance to the nearest edge."""
        if value < self.min:
            return self.min - value
        if value > self.max:
            return value - self.max
        return 0.0


@dataclass(frozen=True, slots=True)
class StyleSpec:
    slug: str
    code: str | None
    display_name: str
    ranges: Mapping[str, tuple[Range, ...]]


@dataclass(frozen=True, slots=True)
class MetricMatch:
    metric: Metric
    value: float
    ranges: tuple[Range, ...]
    status: Status
    delta: float
    """Signed distance from the nearest range edge: negative when low, positive when high."""
    penalty: float


@dataclass(frozen=True, slots=True)
class StyleMatch:
    slug: str
    code: str | None
    display_name: str
    fits: bool
    compared: int
    score: float
    tiebreak: float
    metrics: tuple[MetricMatch, ...]


def match_metric(metric: Metric, value: float, ranges: tuple[Range, ...]) -> MetricMatch:
    nearest = min(ranges, key=lambda r: (r.distance(value), abs(value - r.midpoint())))
    distance = nearest.distance(value)
    if distance == 0:
        return MetricMatch(metric, value, ranges, "in", 0.0, 0.0)
    # Penalty is the smallest normalised miss over all of the metric's ranges.
    penalty = min(r.distance(value) / r.width(metric) for r in ranges)
    status: Status = "low" if value < nearest.min else "high"
    return MetricMatch(
        metric, value, ranges, status, -distance if status == "low" else distance, penalty
    )


def match_style(
    style: StyleSpec, values: Mapping[str, float], weights: Mapping[str, float] | None = None
) -> StyleMatch | None:
    """None when the style has no range for any metric we have a value for."""
    metrics: list[MetricMatch] = []
    score = 0.0
    tiebreak_total = 0.0
    for metric in METRICS:
        ranges = tuple(style.ranges.get(metric, ()))
        if not ranges or metric not in values:
            continue
        result = match_metric(metric, values[metric], ranges)
        metrics.append(result)
        weight = (weights or {}).get(metric, 1.0)
        score += weight * result.penalty
        nearest = min(ranges, key=lambda r: r.distance(values[metric]))
        tiebreak_total += abs(values[metric] - nearest.midpoint()) / nearest.width(metric)
    if not metrics:
        return None
    return StyleMatch(
        slug=style.slug,
        code=style.code,
        display_name=style.display_name,
        fits=all(m.status == "in" for m in metrics),
        compared=len(metrics),
        score=score,
        tiebreak=tiebreak_total / len(metrics),
        metrics=tuple(metrics),
    )


def rank_styles(
    values: Mapping[str, float],
    styles: Iterable[StyleSpec],
    *,
    target_slug: str | None = None,
    limit: int = DEFAULT_LIMIT,
    weights: Mapping[str, float] | None = None,
) -> list[StyleMatch]:
    """The best `limit` matches, plus the target style if it did not make the cut."""
    matches = [m for m in (match_style(s, values, weights) for s in styles) if m is not None]
    matches.sort(key=lambda m: (not m.fits, -m.compared, m.score, m.tiebreak, m.display_name))
    top = matches[:limit]
    if target_slug and all(m.slug != target_slug for m in top):
        top.extend(m for m in matches if m.slug == target_slug)
    return top
