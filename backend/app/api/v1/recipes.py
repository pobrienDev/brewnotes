"""The signed-in user's recipes. Every route is scoped to the caller; other users' get 404."""

from __future__ import annotations

import uuid
from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User
from app.schemas.pagination import DEFAULT_LIMIT, CursorParam, LimitParam, Page
from app.schemas.recipes import RecipeOut, RecipeSummary, RecipeWrite
from app.security.rate_limit import user_rate_limit
from app.security.sessions import current_user
from app.services import recipe_service

router = APIRouter(prefix="/recipes", tags=["recipes"])
write_rate_limit = user_rate_limit("writes", limit=lambda s: s.write_rate_limit_per_minute)


@router.get("", summary="List my recipes, most recently updated first")
def list_recipes(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(current_user)],
    cursor: CursorParam = None,
    limit: LimitParam = DEFAULT_LIMIT,
) -> Page[RecipeSummary]:
    return recipe_service.list_recipes(db, user, cursor=cursor, limit=limit)


@router.post(
    "",
    status_code=HTTPStatus.CREATED,
    dependencies=[Depends(write_rate_limit)],
    summary="Save a new recipe",
)
def create_recipe(
    body: RecipeWrite,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(current_user)],
) -> RecipeOut:
    return recipe_service.create(db, request.app.state.settings, user, body)


@router.get("/{recipe_id}", summary="A recipe with its statistics and style matches")
def read_recipe(
    recipe_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(current_user)],
) -> RecipeOut:
    return recipe_service.get(db, user, recipe_id)


@router.put("/{recipe_id}", dependencies=[Depends(write_rate_limit)], summary="Replace a recipe")
def replace_recipe(
    recipe_id: uuid.UUID,
    body: RecipeWrite,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(current_user)],
) -> RecipeOut:
    return recipe_service.replace(db, user, recipe_id, body)


@router.delete(
    "/{recipe_id}",
    status_code=HTTPStatus.NO_CONTENT,
    dependencies=[Depends(write_rate_limit)],
    summary="Delete a recipe",
)
def delete_recipe(
    recipe_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(current_user)],
) -> Response:
    recipe_service.delete(db, user, recipe_id)
    return Response(status_code=HTTPStatus.NO_CONTENT)
