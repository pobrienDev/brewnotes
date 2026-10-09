"""Style recommendations (Phase 4): the user's average rating per style and style family,
and untried styles close to what they like, each with its reasons."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import Query
from pydantic import Field

from app.domain.recommend import Bitterness, Color, Strength
from app.schemas.base import Schema
from app.schemas.styles import StyleSummary

MAX_SUGGESTIONS = 50

SuggestionLimitParam = Annotated[
    int, Query(ge=1, le=MAX_SUGGESTIONS, description="How many styles to suggest")
]
StrengthParam = Annotated[
    Strength | None, Query(description="Cold-start answer: how strong a beer you like")
]
BitternessParam = Annotated[Bitterness | None, Query(description="Cold-start answer: how bitter")]
ColorParam = Annotated[Color | None, Query(description="Cold-start answer: how dark")]

Metric = Literal["og", "fg", "abv", "ibu", "srm"]


class StyleRef(Schema):
    slug: str
    display_name: str
    category_code: str
    category_name: str


class RatedStyle(StyleRef):
    count: int = Field(description="Tastings tied to this style")
    mean: float = Field(description="Average rating, 0.5 to 5")


class RatedFamily(Schema):
    category_code: str
    category_name: str
    count: int = Field(description="Tastings tied to styles in this category")
    mean: float = Field(description="Average rating over those tastings")


class Reason(Schema):
    """Why a style is suggested: a style the user rated well, or their cold-start answers."""

    kind: Literal["style", "answers"]
    style: StyleRef | None = Field(description="The rated style; null for the answers")
    rating: float | None = Field(description="The user's average rating of that style")
    count: int = Field(description="How many tastings that rating rests on")
    distance: float = Field(
        description="0 for identical statistics, about 0.05 for a near twin, "
        "0.25 for something quite different"
    )


class Difference(Schema):
    metric: Metric
    direction: Literal["higher", "lower"]


class StyleSuggestion(Schema):
    style: StyleSummary
    score: float = Field(description="Ranking score; only positive scores are suggested")
    because: list[Reason] = Field(description="Strongest reason first")
    differences: list[Difference] = Field(
        description="Where the style's statistics differ noticeably from the first reason's"
    )


class StyleRecommendations(Schema):
    tastings_with_style: int = Field(description="Tastings that could be tied to a style")
    min_tastings: int = Field(description="Below this the cold-start questions are asked")
    cold_start: bool
    answered: bool = Field(description="Whether any cold-start answer was given")
    styles: list[RatedStyle] = Field(description="Average rating per style, best first")
    families: list[RatedFamily] = Field(description="Average rating per category, best first")
    suggestions: list[StyleSuggestion] = Field(description="Untried styles, best first")
