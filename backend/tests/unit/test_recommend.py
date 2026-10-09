"""Style recommendations: the distance is a metric, affinities behave, ranking follows the
rules, and the real BJCP data gives sensible, explained suggestions (plan Phase 4)."""

from __future__ import annotations

import math
from collections.abc import Iterable
from itertools import pairwise
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.domain.recommend import (
    ANSWERS_SLUG,
    BITTERNESS_RANGES,
    COLOR_RANGES,
    STRENGTH_RANGES,
    Answers,
    Preference,
    StyleProfile,
    StyleRating,
    affinity,
    differences,
    family_ratings,
    preference_from_answers,
    preferences_from_ratings,
    profile_from_answers,
    recommend,
    score_style,
    style_distance,
)
from app.domain.style_match import METRICS, Range
from app.services.seed_service import DATA_DIR, load_json

BOUNDS: dict[str, tuple[float, float]] = {
    "og": (1.020, 1.140),
    "fg": (0.990, 1.045),
    "abv": (2.0, 15.0),
    "ibu": (0.0, 120.0),
    "srm": (1.0, 45.0),
}


# -- strategies ---------------------------------------------------------------------------


def one_range(metric: str) -> st.SearchStrategy[Range]:
    low, high = BOUNDS[metric]
    values = st.floats(low, high, allow_nan=False, allow_infinity=False)
    return st.tuples(values, values).map(lambda pair: Range(min(pair), max(pair)))


def ranges_for(metric: str, *, max_ranges: int) -> st.SearchStrategy[tuple[Range, ...]]:
    return st.lists(one_range(metric), min_size=1, max_size=max_ranges).map(tuple)


slugs = st.text(alphabet="abcdefghijklmnopqrstuvwxyz-", min_size=1, max_size=12)


def profiles(
    *, max_ranges: int = 1, metrics: Iterable[str] = METRICS
) -> st.SearchStrategy[StyleProfile]:
    chosen = tuple(metrics)
    return st.builds(
        lambda slug, ranges: StyleProfile(slug, slug.upper(), "1", "Family", ranges),
        slugs,
        st.fixed_dictionaries({m: ranges_for(m, max_ranges=max_ranges) for m in chosen}),
    )


single_range_profiles = profiles()
any_profiles = profiles(max_ranges=3)
ratings = st.floats(0.5, 5.0, allow_nan=False)
counts = st.integers(1, 50)


def distinct(
    strategy: st.SearchStrategy[StyleProfile], **kwargs: Any
) -> st.SearchStrategy[list[StyleProfile]]:
    return st.lists(strategy, unique_by=lambda p: p.slug, **kwargs)


# -- the distance -----------------------------------------------------------------------


@given(any_profiles, any_profiles)
def test_distance_is_symmetric_finite_and_non_negative(a: StyleProfile, b: StyleProfile) -> None:
    ab, ba = style_distance(a, b), style_distance(b, a)
    assert ab is not None and ba is not None
    assert ab == pytest.approx(ba)
    assert ab >= 0 and math.isfinite(ab)


@given(any_profiles)
def test_distance_to_self_is_zero(a: StyleProfile) -> None:
    assert style_distance(a, a) == 0


@given(single_range_profiles, single_range_profiles)
def test_distance_is_zero_only_for_identical_ranges(a: StyleProfile, b: StyleProfile) -> None:
    same = all(a.ranges[m][0] == b.ranges[m][0] for m in METRICS)
    distance = style_distance(a, b)
    assert distance is not None
    assert (distance == 0) == same


@settings(max_examples=300)
@given(single_range_profiles, single_range_profiles, single_range_profiles)
def test_triangle_inequality(a: StyleProfile, b: StyleProfile, c: StyleProfile) -> None:
    ab, bc, ac = style_distance(a, b), style_distance(b, c), style_distance(a, c)
    assert ab is not None and bc is not None and ac is not None
    assert ac <= ab + bc + 1e-9


@given(profiles(metrics=["og", "fg"]), profiles(metrics=["ibu", "srm"]))
def test_no_metric_in_common_is_incomparable(a: StyleProfile, b: StyleProfile) -> None:
    assert style_distance(a, b) is None


def test_multi_range_styles_use_their_nearest_range() -> None:
    saison = StyleProfile(
        "saison",
        "25B Saison",
        "25",
        "Belgian Ale",
        {"abv": (Range(3.5, 5.0, "table"), Range(5.0, 7.0, "standard"), Range(7.0, 9.5, "super"))},
    )
    table = StyleProfile("t", "T", "1", "F", {"abv": (Range(3.5, 5.0),)})
    super_ = StyleProfile("s", "S", "1", "F", {"abv": (Range(7.0, 9.5),)})
    middle = StyleProfile("m", "M", "1", "F", {"abv": (Range(6.0, 7.0),)})
    assert style_distance(saison, table) == 0
    assert style_distance(saison, super_) == 0
    # Nearest is the standard range: midpoints 6 and 6.5, half-widths 1 and 0.5.
    assert style_distance(saison, middle) == pytest.approx((0.5 + 0.5 * 0.5) / 12.0)


def test_ibu_and_srm_are_compared_on_a_square_root_scale() -> None:
    def ibu(low: float, high: float) -> StyleProfile:
        return StyleProfile("x", "X", "1", "F", {"ibu": (Range(low, high),)})

    low_end = style_distance(ibu(10, 10), ibu(25, 25))
    high_end = style_distance(ibu(60, 60), ibu(75, 75))
    assert low_end is not None and high_end is not None
    assert low_end > high_end  # the same 15 IBU is a bigger step at the bottom of the scale


# -- affinity ---------------------------------------------------------------------------------


@given(ratings, counts)
def test_affinity_is_bounded(mean: float, count: int) -> None:
    assert -1.0 <= affinity(mean, count) <= 1.0


@given(ratings, ratings, counts)
def test_affinity_grows_with_the_rating(first: float, second: float, count: int) -> None:
    low, high = sorted((first, second))
    assert affinity(low, count) <= affinity(high, count)


@given(counts, counts)
def test_more_tastings_mean_more_confidence(first: int, second: int) -> None:
    low, high = sorted((first, second))
    assert affinity(5.0, low) <= affinity(5.0, high)
    assert affinity(1.0, low) >= affinity(1.0, high)


def test_affinity_anchors() -> None:
    assert affinity(3.0, 10) == 0
    assert affinity(5.0, 1) == pytest.approx(0.5)
    assert affinity(5.0, 999) == pytest.approx(1.0, abs=0.002)
    assert affinity(1.0, 1) == pytest.approx(-0.5)
    assert affinity(0.5, 1) == pytest.approx(-0.5)  # clamped: 0.5 is no worse than 1
    assert affinity(4.0, 0) == 0


# -- ranking ----------------------------------------------------------------------------------


@settings(max_examples=200)
@given(
    distinct(single_range_profiles, min_size=1, max_size=20),
    st.lists(st.tuples(single_range_profiles, ratings, counts), max_size=5),
    st.integers(1, 10),
)
def test_recommend_obeys_the_rules(
    candidates: list[StyleProfile],
    rated: list[tuple[StyleProfile, float, int]],
    limit: int,
) -> None:
    preferences = preferences_from_ratings([StyleRating(p, n, mean) for p, mean, n in rated])
    tried = {p.slug for p, _, _ in rated}
    suggestions = recommend(candidates, preferences, exclude=tried, limit=limit)
    assert len(suggestions) <= limit
    slugs = [s.style.slug for s in suggestions]
    assert len(set(slugs)) == len(slugs)
    assert not set(slugs) & tried
    scores = [s.score for s in suggestions]
    assert scores == sorted(scores, reverse=True)
    for suggestion in suggestions:
        assert suggestion.score > 0 and math.isfinite(suggestion.score)
        assert suggestion.because, "every suggestion has a reason"
        assert all(i.contribution > 0 for i in suggestion.because)
        assert [i.contribution for i in suggestion.because] == sorted(
            (i.contribution for i in suggestion.because), reverse=True
        )
        assert suggestion.because[0].preference.affinity > 0


@given(distinct(single_range_profiles, min_size=1, max_size=20), single_range_profiles, counts)
def test_one_liked_style_ranks_candidates_by_distance(
    candidates: list[StyleProfile], liked: StyleProfile, count: int
) -> None:
    preference = Preference(liked, affinity(5.0, count), rating=5.0, count=count)
    suggestions = recommend(candidates, [preference], exclude={liked.slug}, limit=100)
    distances = [s.because[0].distance for s in suggestions]
    assert distances == sorted(distances)
    assert len(suggestions) == len([c for c in candidates if c.slug != liked.slug])


@given(distinct(single_range_profiles, min_size=1, max_size=10), single_range_profiles)
def test_a_twin_of_a_liked_style_comes_first(
    candidates: list[StyleProfile], liked: StyleProfile
) -> None:
    twin = StyleProfile("twin", "Twin", "1", "F", liked.ranges)
    pool = [c for c in candidates if c.slug != "twin"] + [twin]
    preference = Preference(liked, 0.8, rating=4.6, count=4)
    best = recommend(pool, [preference], exclude={liked.slug}, limit=1)[0]
    assert best.score == pytest.approx(0.8)  # exp(0) * affinity
    assert best.because[0].distance == 0
    assert best.differences == {}


@given(
    distinct(single_range_profiles, min_size=1, max_size=10),
    st.lists(st.tuples(single_range_profiles, st.floats(0.5, 3.0), counts), min_size=1, max_size=4),
)
def test_only_disliked_styles_suggest_nothing(
    candidates: list[StyleProfile], rated: list[tuple[StyleProfile, float, int]]
) -> None:
    preferences = preferences_from_ratings([StyleRating(p, n, mean) for p, mean, n in rated])
    assert recommend(candidates, preferences) == []


@given(
    distinct(single_range_profiles, min_size=2, max_size=10),
    st.lists(st.tuples(single_range_profiles, ratings, counts), min_size=1, max_size=4),
    st.floats(0.1, 10.0),
)
def test_scaling_every_affinity_keeps_the_order(
    candidates: list[StyleProfile], rated: list[tuple[StyleProfile, float, int]], factor: float
) -> None:
    preferences = preferences_from_ratings([StyleRating(p, n, mean) for p, mean, n in rated])
    scaled = [Preference(p.profile, p.affinity * factor, p.rating, p.count) for p in preferences]
    before = [s.style.slug for s in recommend(candidates, preferences, limit=100)]
    after = [s.style.slug for s in recommend(candidates, scaled, limit=100)]
    assert before == after


def test_a_candidate_with_nothing_in_common_is_never_suggested() -> None:
    hoppy = StyleProfile("h", "H", "1", "F", {"ibu": (Range(40, 70),)})
    dark = StyleProfile("d", "D", "1", "F", {"srm": (Range(30, 40),)})
    assert score_style(dark, [Preference(hoppy, 1.0)]) == (0.0, [])
    assert recommend([dark], [Preference(hoppy, 1.0)]) == []


@given(single_range_profiles, single_range_profiles)
def test_differences_are_antisymmetric(a: StyleProfile, b: StyleProfile) -> None:
    forward, backward = differences(a, b), differences(b, a)
    assert set(forward) == set(backward)
    for metric, direction in forward.items():
        assert backward[metric] == ("lower" if direction == "higher" else "higher")
    assert differences(a, a) == {}


# -- families and answers ---------------------------------------------------------------------


def test_family_ratings_weight_every_tasting_equally() -> None:
    ipa = StyleProfile("american-ipa", "21A American IPA", "21", "IPA", {})
    rye = StyleProfile("rye-ipa", "21B Rye IPA", "21", "IPA", {})
    stout = StyleProfile("irish-stout", "15B Irish Stout", "15", "Irish Beer", {})
    families = family_ratings(
        [StyleRating(ipa, 3, 5.0), StyleRating(rye, 1, 1.0), StyleRating(stout, 2, 4.5)]
    )
    assert [(f.category_code, f.category_name, f.count) for f in families] == [
        ("15", "Irish Beer", 2),
        ("21", "IPA", 4),
    ]
    assert families[0].mean == 4.5
    assert families[1].mean == pytest.approx((3 * 5.0 + 1.0) / 4)


def test_answers_become_a_pseudo_style() -> None:
    assert profile_from_answers(Answers()) is None
    assert preference_from_answers(Answers()) is None
    assert Answers().any is False
    profile = profile_from_answers(Answers(strength="strong", color="dark"))
    assert profile is not None
    assert profile.slug == ANSWERS_SLUG
    assert set(profile.ranges) == {"abv", "og", "srm"}
    assert profile.ranges["abv"] == (Range(*STRENGTH_RANGES["strong"]["abv"]),)
    assert profile.ranges["srm"] == (Range(*COLOR_RANGES["dark"]["srm"]),)
    only_bitter = profile_from_answers(Answers(bitterness="bitter"))
    assert only_bitter is not None
    assert only_bitter.ranges == {"ibu": (Range(*BITTERNESS_RANGES["bitter"]["ibu"]),)}
    preference = preference_from_answers(Answers(bitterness="bitter"))
    assert preference is not None and preference.from_answers and preference.affinity > 0


def test_answer_ranges_are_contiguous_and_ordered() -> None:
    tables = ((STRENGTH_RANGES, "abv"), (BITTERNESS_RANGES, "ibu"), (COLOR_RANGES, "srm"))
    for table, metric in tables:
        spans = [entry[metric] for entry in table.values()]
        for (_, high), (low, _) in pairwise(spans):
            assert high == low


# -- the real guidelines --------------------------------------------------------------------


def bjcp_profiles() -> dict[str, StyleProfile]:
    """Every BJCP 2021 style with ranges, from the seed file (same shape as the API's)."""
    data = load_json(DATA_DIR / "styles_bjcp_2021.json")
    result: dict[str, StyleProfile] = {}
    for category in data["categories"]:
        for style in category["styles"]:
            entries = [(style, None)] + [(v, style) for v in style.get("variants", [])]
            for raw, parent in entries:
                ranges = {
                    metric: tuple(Range(float(r[0]), float(r[1])) for r in rs)
                    for metric, rs in raw.get("ranges", {}).items()
                }
                if not ranges:
                    continue
                name = (
                    f"{style['code']} {style['name']}: {raw['name']}"
                    if parent is not None
                    else f"{raw['code']} {raw['name']}"
                )
                result[raw["slug"]] = StyleProfile(
                    raw["slug"], name, category["code"], category["name"], ranges
                )
    return result


BJCP = bjcp_profiles()


def names(suggestions: Iterable[Any]) -> list[str]:
    return [s.style.display_name for s in suggestions]


def test_every_bjcp_style_with_ranges_has_all_five_metrics() -> None:
    assert len(BJCP) == 102
    assert all(set(p.ranges) == set(METRICS) for p in BJCP.values())


def test_ipa_lovers_get_ipas_and_bitters() -> None:
    preferences = preferences_from_ratings([StyleRating(BJCP["american-ipa"], 4, 4.5)])
    suggested = names(recommend(BJCP.values(), preferences, exclude={"american-ipa"}, limit=6))
    assert "12C English IPA" in suggested[:3]
    assert "18B American Pale Ale" in suggested
    assert any("Specialty IPA" in n for n in suggested)


def test_stout_drinkers_get_dark_beers() -> None:
    preferences = preferences_from_ratings([StyleRating(BJCP["irish-stout"], 3, 4.0)])
    suggested = names(recommend(BJCP.values(), preferences, exclude={"irish-stout"}, limit=5))
    assert "16B Oatmeal Stout" in suggested
    assert "13C English Porter" in suggested
    assert not any("Lager" in n and "Dark" not in n for n in suggested)


def test_ten_tastings_give_sensible_explained_suggestions() -> None:
    """The plan's "done when": a mix of liked and disliked styles."""
    rated = [
        StyleRating(BJCP["american-ipa"], 4, 4.5),
        StyleRating(BJCP["irish-stout"], 3, 4.0),
        StyleRating(BJCP["american-lager"], 2, 2.0),
        StyleRating(BJCP["saison"], 1, 3.5),
    ]
    preferences = preferences_from_ratings(rated)
    tried = {r.profile.slug for r in rated}
    suggestions = recommend(BJCP.values(), preferences, exclude=tried, limit=10)
    suggested = names(suggestions)
    assert len(suggested) == 10
    assert "12C English IPA" in suggested[:3]
    assert "13C English Porter" in suggested
    assert "1A American Light Lager" not in suggested
    assert "2A International Pale Lager" not in suggested
    for suggestion in suggestions:
        assert suggestion.because[0].preference.profile.slug in {"american-ipa", "irish-stout"}
        assert suggestion.because[0].preference.rating in {4.5, 4.0}
    strong_bitter = next(s for s in suggestions if s.style.slug == "strong-bitter")
    assert strong_bitter.because[0].preference.profile.slug == "american-ipa"
    assert strong_bitter.differences == {
        "og": "lower",
        "abv": "lower",
        "ibu": "lower",
        "srm": "higher",
    }


def test_cold_start_answers_alone_give_suggestions() -> None:
    strong_bitter_pale = preference_from_answers(Answers("strong", "bitter", "pale"))
    assert strong_bitter_pale is not None
    suggested = names(recommend(BJCP.values(), [strong_bitter_pale], limit=5))
    assert any("IPA" in n for n in suggested[:2])
    assert "22A Double IPA" in suggested
    session_soft_dark = preference_from_answers(Answers("session", "soft", "dark"))
    assert session_soft_dark is not None
    suggested = names(recommend(BJCP.values(), [session_soft_dark], limit=6))
    assert "13A Dark Mild" in suggested
    assert not any("IPA" in n for n in suggested)
