"""Style recommendations from the user's own ratings (plan Phase 4, decision D7).

Pure functions over (style ranges, the user's average rating per style, the answers to the
cold-start questions). No I/O.

How it works:

- Two styles are compared by their vital statistics. For each metric a range is reduced to
  a midpoint and a half-width and two ranges are |Δmidpoint| + ½|Δhalf-width| apart (a metric
  on intervals); where a style has several labelled ranges for a metric (Saison's table,
  standard and super ABV) the nearest pair counts. IBU and SRM are compared on a square-root
  scale, so 10 against 25 IBU counts for more than 60 against 75. Each metric is normalised
  by its spread across the guidelines and the five are combined as a weighted root mean
  square (OG and FG share one weight, since strength is already measured by ABV).
- Every style the user has rated becomes a preference with an affinity in [-1, 1]: 3 out of 5
  is neutral, 5 is +1, 1 is -1, and a style tasted once counts half as much as one tasted
  many times. The cold-start answers become one more preference built from fixed ranges.
- A candidate (a style with ranges that the user has not rated) scores
  sum(affinity * exp(-distance / TAU)) over the preferences. Candidates with a positive score are
  ranked by it; the preferences that pushed a candidate up are its reasons, and the
  differences between the candidate and its strongest reason explain what to expect.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Literal

from app.domain.style_match import METRICS, Metric, Range

# Spread of each metric across the BJCP 2021 styles, in the compared (transformed) units.
SCALE: dict[str, float] = {"og": 0.10, "fg": 0.05, "abv": 12.0, "ibu": 10.0, "srm": 5.0}
WEIGHTS: dict[str, float] = {"og": 0.5, "fg": 0.5, "abv": 1.0, "ibu": 1.0, "srm": 1.0}
# How much a difference in range width counts next to a difference in midpoint.
WIDTH_WEIGHT = 0.5
# Characteristic distance: a style this far away has a third of the influence of a twin.
TAU = 0.12
# Ratings: 3 out of 5 is neutral, the two steps up to 5 give the full affinity.
NEUTRAL_RATING = 3.0
RATING_SPAN = 2.0
# Affinity of the cold-start answers: a little less than a style rated 5 several times.
ANSWERS_AFFINITY = 0.75
# A midpoint difference this large (as a fraction of the metric's spread) is worth saying.
NOTABLE_DIFFERENCE = 0.08
MAX_REASONS = 2
DEFAULT_LIMIT = 10

Direction = Literal["higher", "lower"]
Strength = Literal["session", "standard", "strong"]
Bitterness = Literal["soft", "balanced", "bitter"]
Color = Literal["pale", "amber", "dark"]

# The cold-start questions, as the ranges each answer stands for.
STRENGTH_RANGES: dict[str, dict[str, tuple[float, float]]] = {
    "session": {"abv": (3.0, 4.5), "og": (1.030, 1.046)},
    "standard": {"abv": (4.5, 6.5), "og": (1.046, 1.065)},
    "strong": {"abv": (6.5, 10.0), "og": (1.065, 1.100)},
}
BITTERNESS_RANGES: dict[str, dict[str, tuple[float, float]]] = {
    "soft": {"ibu": (5.0, 20.0)},
    "balanced": {"ibu": (20.0, 40.0)},
    "bitter": {"ibu": (40.0, 80.0)},
}
COLOR_RANGES: dict[str, dict[str, tuple[float, float]]] = {
    "pale": {"srm": (2.0, 8.0)},
    "amber": {"srm": (8.0, 18.0)},
    "dark": {"srm": (18.0, 40.0)},
}
ANSWERS_SLUG = "answers"


@dataclass(frozen=True, slots=True)
class StyleProfile:
    slug: str
    display_name: str
    category_code: str
    category_name: str
    ranges: Mapping[str, tuple[Range, ...]]

    def envelope(self, metric: str) -> Range | None:
        """Lowest min to highest max across the metric's labelled ranges."""
        ranges = self.ranges.get(metric, ())
        if not ranges:
            return None
        return Range(min(r.min for r in ranges), max(r.max for r in ranges))


@dataclass(frozen=True, slots=True)
class StyleRating:
    """The user's average rating for one style."""

    profile: StyleProfile
    count: int
    mean: float


@dataclass(frozen=True, slots=True)
class FamilyRating:
    category_code: str
    category_name: str
    count: int
    mean: float


@dataclass(frozen=True, slots=True)
class Answers:
    strength: Strength | None = None
    bitterness: Bitterness | None = None
    color: Color | None = None

    @property
    def any(self) -> bool:
        return self.strength is not None or self.bitterness is not None or self.color is not None


@dataclass(frozen=True, slots=True)
class Preference:
    """Something the user is known to like (affinity > 0) or dislike (< 0)."""

    profile: StyleProfile
    affinity: float
    rating: float | None = None
    count: int = 0

    @property
    def from_answers(self) -> bool:
        return self.rating is None


@dataclass(frozen=True, slots=True)
class Influence:
    preference: Preference
    distance: float
    contribution: float


@dataclass(frozen=True, slots=True)
class Suggestion:
    style: StyleProfile
    score: float
    because: tuple[Influence, ...]
    """Preferences that pushed the style up, strongest first (at most MAX_REASONS)."""
    differences: Mapping[str, Direction]
    """Metrics on which the style differs noticeably from its strongest reason."""


# -- distance --------------------------------------------------------------------------------


def transform(metric: str, value: float) -> float:
    """The scale a metric is compared on: square root for IBU and SRM, identity otherwise."""
    if metric in ("ibu", "srm"):
        return math.sqrt(max(value, 0.0))
    return value


def interval_distance(a: Range, b: Range) -> float:
    """|Δmidpoint| + WIDTH_WEIGHT * |Δhalf-width|: zero only for identical intervals."""
    return abs(a.midpoint() - b.midpoint()) + WIDTH_WEIGHT * abs(
        (a.max - a.min) / 2 - (b.max - b.min) / 2
    )


def metric_distance(metric: str, a: Iterable[Range], b: Iterable[Range]) -> float:
    """Normalised distance between two styles for one metric: the nearest pair of ranges."""
    ta = [Range(transform(metric, r.min), transform(metric, r.max)) for r in a]
    tb = [Range(transform(metric, r.min), transform(metric, r.max)) for r in b]
    return min(interval_distance(ra, rb) for ra in ta for rb in tb) / SCALE[metric]


def style_distance(
    a: StyleProfile, b: StyleProfile, *, weights: Mapping[str, float] = WEIGHTS
) -> float | None:
    """Weighted root mean square over the metrics both styles have; None when there are
    none in common."""
    total = 0.0
    weight_sum = 0.0
    for metric in METRICS:
        ra, rb = a.ranges.get(metric, ()), b.ranges.get(metric, ())
        if not ra or not rb:
            continue
        weight = weights.get(metric, 1.0)
        distance = metric_distance(metric, ra, rb)
        total += weight * distance * distance
        weight_sum += weight
    if weight_sum == 0:
        return None
    return math.sqrt(total / weight_sum)


# -- preferences -----------------------------------------------------------------------------


def affinity(mean: float, count: int) -> float:
    """How much the user likes a style, in [-1, 1]. 3 of 5 is neutral; the first tasting
    counts half, many tastings count fully."""
    if count <= 0:
        return 0.0
    raw = (mean - NEUTRAL_RATING) / RATING_SPAN
    raw = max(-1.0, min(1.0, raw))
    return raw * count / (count + 1)


def preferences_from_ratings(ratings: Iterable[StyleRating]) -> list[Preference]:
    return [
        Preference(r.profile, affinity(r.mean, r.count), rating=r.mean, count=r.count)
        for r in ratings
        if r.count > 0
    ]


def profile_from_answers(answers: Answers) -> StyleProfile | None:
    """The cold-start answers as a pseudo-style; None when nothing was answered."""
    ranges: dict[str, tuple[Range, ...]] = {}
    for value, table in (
        (answers.strength, STRENGTH_RANGES),
        (answers.bitterness, BITTERNESS_RANGES),
        (answers.color, COLOR_RANGES),
    ):
        if value is None:
            continue
        for metric, (low, high) in table[value].items():
            ranges[metric] = (Range(low, high),)
    if not ranges:
        return None
    return StyleProfile(ANSWERS_SLUG, "your answers", "", "", ranges)


def preference_from_answers(answers: Answers) -> Preference | None:
    profile = profile_from_answers(answers)
    if profile is None:
        return None
    return Preference(profile, ANSWERS_AFFINITY)


def family_ratings(ratings: Iterable[StyleRating]) -> list[FamilyRating]:
    """Average rating per style family (BJCP category), all tastings weighted equally;
    best first."""
    totals: dict[str, tuple[str, int, float]] = {}
    for r in ratings:
        name, count, total = totals.get(r.profile.category_code, (r.profile.category_name, 0, 0.0))
        totals[r.profile.category_code] = (name, count + r.count, total + r.count * r.mean)
    families = [
        FamilyRating(code, name, count, total / count)
        for code, (name, count, total) in totals.items()
        if count > 0
    ]
    families.sort(key=lambda f: (-f.mean, -f.count, f.category_code))
    return families


# -- scoring ---------------------------------------------------------------------------------


def differences(candidate: StyleProfile, reference: StyleProfile) -> dict[str, Direction]:
    """Metrics on which the candidate's midpoint differs noticeably from the reference's."""
    result: dict[str, Direction] = {}
    for metric in METRICS:
        ec, er = candidate.envelope(metric), reference.envelope(metric)
        if ec is None or er is None:
            continue
        delta = (transform(metric, ec.midpoint()) - transform(metric, er.midpoint())) / SCALE[
            metric
        ]
        if abs(delta) >= NOTABLE_DIFFERENCE:
            result[metric] = "higher" if delta > 0 else "lower"
    return result


def score_style(
    candidate: StyleProfile, preferences: Iterable[Preference], *, tau: float = TAU
) -> tuple[float, list[Influence]]:
    """The candidate's score and every preference's contribution, strongest first."""
    influences: list[Influence] = []
    for preference in preferences:
        distance = style_distance(candidate, preference.profile)
        if distance is None:
            continue
        contribution = preference.affinity * math.exp(-distance / tau)
        influences.append(Influence(preference, distance, contribution))
    influences.sort(key=lambda i: -i.contribution)
    return sum(i.contribution for i in influences), influences


def recommend(
    candidates: Iterable[StyleProfile],
    preferences: Iterable[Preference],
    *,
    exclude: frozenset[str] | set[str] = frozenset(),
    limit: int = DEFAULT_LIMIT,
    tau: float = TAU,
) -> list[Suggestion]:
    """The best `limit` untried styles, best first; only styles with a positive score."""
    prefs = list(preferences)
    suggestions: list[Suggestion] = []
    for candidate in candidates:
        if candidate.slug in exclude:
            continue
        score, influences = score_style(candidate, prefs, tau=tau)
        if score <= 0:
            continue
        because = tuple(i for i in influences if i.contribution > 0)[:MAX_REASONS]
        suggestions.append(
            Suggestion(
                candidate,
                score,
                because,
                differences(candidate, because[0].preference.profile) if because else {},
            )
        )
    suggestions.sort(key=lambda s: (-s.score, s.style.display_name))
    return suggestions[:limit]


__all__ = [
    "ANSWERS_SLUG",
    "DEFAULT_LIMIT",
    "Answers",
    "Bitterness",
    "Color",
    "Direction",
    "FamilyRating",
    "Influence",
    "Metric",
    "Preference",
    "Strength",
    "StyleProfile",
    "StyleRating",
    "Suggestion",
    "affinity",
    "differences",
    "family_ratings",
    "preference_from_answers",
    "preferences_from_ratings",
    "profile_from_answers",
    "recommend",
    "score_style",
    "style_distance",
]
