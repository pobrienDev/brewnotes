"""Stateless calculator endpoints. Public, rate limited per IP."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.calc import CalcResult, ScaleRequest, ScaleResult
from app.schemas.recipe import RecipeInput
from app.security.rate_limit import rate_limit
from app.services import calc_service

router = APIRouter(prefix="/calc", tags=["calc"])
calc_rate_limit = rate_limit("calc", limit=60)


@router.post(
    "",
    dependencies=[Depends(calc_rate_limit)],
    summary="Statistics and style matches for a recipe body",
)
def calculate(recipe: RecipeInput, db: Annotated[Session, Depends(get_db)]) -> CalcResult:
    return calc_service.calculate(db, recipe)


@router.post(
    "/scale",
    dependencies=[Depends(calc_rate_limit)],
    summary="Scale a recipe to a new batch volume and/or brewhouse efficiency",
)
def scale(request: ScaleRequest) -> ScaleResult:
    return calc_service.scale(request)
