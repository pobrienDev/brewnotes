"""Style suggestions from the user's own tastings (plan Phase 4, decision D7).

Ratings come from tastings of beers that carry a style and of batches whose recipe snapshot
names a target style. The scoring itself is `app.domain.recommend`; this module only
gathers the inputs and shapes the answer.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.config import Settings
from app.domain import recommend as rec
from app.domain.style_match import Range
from app.models import Style, User
from app.repositories import style_repo, tasting_repo
from app.schemas.recommendations import (
    Difference,
    RatedFamily,
    RatedStyle,
    Reason,
    StyleRecommendations,
    StyleRef,
    StyleSuggestion,
)
from app.schemas.styles import StyleSummary


def profile_of(style: Style) -> rec.StyleProfile:
    ranges: dict[str, list[Range]] = {}
    for r in style.ranges:
        ranges.setdefault(r.metric, []).append(Range(r.min, r.max, r.label))
    return rec.StyleProfile(
        slug=style.slug,
        display_name=style.display_name,
        category_code=style.category_code,
        category_name=style.category_name,
        ranges={metric: tuple(rs) for metric, rs in ranges.items()},
    )


def _ref(profile: rec.StyleProfile) -> StyleRef:
    return StyleRef(
        slug=profile.slug,
        display_name=profile.display_name,
        category_code=profile.category_code,
        category_name=profile.category_name,
    )


def _reason(influence: rec.Influence) -> Reason:
    preference = influence.preference
    if preference.from_answers:
        return Reason(kind="answers", style=None, rating=None, count=0, distance=influence.distance)
    return Reason(
        kind="style",
        style=_ref(preference.profile),
        rating=preference.rating,
        count=preference.count,
        distance=influence.distance,
    )


def _suggestion(suggestion: rec.Suggestion, styles: dict[str, Style]) -> StyleSuggestion:
    return StyleSuggestion(
        style=StyleSummary.from_model(styles[suggestion.style.slug]),
        score=suggestion.score,
        because=[_reason(i) for i in suggestion.because],
        differences=[
            Difference(metric=metric, direction=direction)  # type: ignore[arg-type]
            for metric, direction in suggestion.differences.items()
        ],
    )


def recommend_styles(
    db: Session, settings: Settings, user: User, *, answers: rec.Answers, limit: int
) -> StyleRecommendations:
    stats = tasting_repo.style_ratings(db, user.id)
    styles = style_repo.list_all(db)
    profiles = {style.id: profile_of(style) for style in styles}
    ratings = [
        rec.StyleRating(profiles[style_id], count, mean)
        for style_id, (count, mean) in stats.items()
        if style_id in profiles
    ]
    ratings.sort(key=lambda r: (-r.mean, -r.count, r.profile.display_name))

    preferences = rec.preferences_from_ratings(ratings)
    from_answers = rec.preference_from_answers(answers)
    if from_answers is not None:
        preferences.append(from_answers)
    tried = {r.profile.slug for r in ratings}
    candidates = [profiles[style.id] for style in styles if style.ranges]
    suggestions = rec.recommend(candidates, preferences, exclude=tried, limit=limit)

    by_slug = {style.slug: style for style in styles}
    total = sum(r.count for r in ratings)
    return StyleRecommendations(
        tastings_with_style=total,
        min_tastings=settings.recommendation_min_tastings,
        cold_start=total < settings.recommendation_min_tastings,
        answered=from_answers is not None,
        styles=[
            RatedStyle(**_ref(r.profile).model_dump(), count=r.count, mean=r.mean) for r in ratings
        ],
        families=[
            RatedFamily(
                category_code=f.category_code,
                category_name=f.category_name,
                count=f.count,
                mean=f.mean,
            )
            for f in rec.family_ratings(ratings)
        ],
        suggestions=[_suggestion(s, by_slug) for s in suggestions],
    )
