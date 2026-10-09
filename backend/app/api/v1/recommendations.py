"""Style recommendations for the signed-in user, from their own tastings only."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.domain.recommend import DEFAULT_LIMIT, Answers
from app.models import User
from app.schemas.recommendations import (
    BitternessParam,
    ColorParam,
    StrengthParam,
    StyleRecommendations,
    SuggestionLimitParam,
)
from app.security.sessions import current_user
from app.services import recommendation_service

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


@router.get(
    "/styles",
    summary="Styles to try, from my ratings",
    description=(
        "The user's average rating per style and per BJCP category, and untried styles whose "
        "vital statistics are closest to the styles they rated well, each with its reasons. "
        "With fewer than `min_tastings` style-rated tastings the answer is a cold start: pass "
        "`strength`, `bitterness` and `color` to get suggestions from those answers instead."
    ),
)
def recommend_styles(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(current_user)],
    limit: SuggestionLimitParam = DEFAULT_LIMIT,
    strength: StrengthParam = None,
    bitterness: BitternessParam = None,
    color: ColorParam = None,
) -> StyleRecommendations:
    return recommendation_service.recommend_styles(
        db,
        request.app.state.settings,
        user,
        answers=Answers(strength=strength, bitterness=bitterness, color=color),
        limit=limit,
    )
