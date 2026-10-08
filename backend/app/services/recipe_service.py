"""Saved recipes: CRUD with ownership, quotas and catalog reference checks."""

from __future__ import annotations

import uuid
from datetime import datetime
from http import HTTPStatus
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.domain import brewmath as bm
from app.domain.style_match import rank_styles
from app.errors import FieldError, ValidationProblemError
from app.models import (
    Fermentable,
    Hop,
    Recipe,
    RecipeFermentable,
    RecipeHop,
    RecipeYeast,
    Style,
    User,
    Yeast,
)
from app.repositories import catalog_repo, recipe_repo, style_repo
from app.schemas.calc import RecipeStatsOut, StyleMatchOut
from app.schemas.pagination import Page, decode_cursor, encode_cursor
from app.schemas.recipe import RecipeInput
from app.schemas.recipes import (
    RecipeFermentableOut,
    RecipeHopOut,
    RecipeOut,
    RecipeSummary,
    RecipeWrite,
    RecipeYeastOut,
)
from app.schemas.styles import StyleSummary
from app.services import calc_service


def _not_found() -> HTTPException:
    return HTTPException(HTTPStatus.NOT_FOUND, detail="No such recipe.")


def _calc_input(recipe: Recipe) -> RecipeInput:
    return RecipeInput.model_validate(
        {
            "batch_volume_l": recipe.batch_volume_l,
            "pre_boil_volume_l": recipe.pre_boil_volume_l,
            "boil_time_min": recipe.boil_time_min,
            "brewhouse_efficiency_pct": recipe.brewhouse_efficiency_pct,
            "steep_efficiency_pct": recipe.steep_efficiency_pct,
            "fermentables": [
                {
                    "name": f.name,
                    "amount_kg": f.amount_kg,
                    "ppg": f.ppg,
                    "color_lovibond": f.color_lovibond,
                    "addition": f.addition,
                }
                for f in recipe.fermentables
            ],
            "hops": [
                {
                    "name": h.name,
                    "amount_g": h.amount_g,
                    "alpha_pct": h.alpha_pct,
                    "use": h.use,
                    "time_min": h.time_min,
                    "dry_hop_days": h.dry_hop_days,
                }
                for h in recipe.hops
            ],
            "yeasts": [
                {"name": y.name, "attenuation_pct": y.attenuation_pct} for y in recipe.yeasts
            ],
        }
    )


def stats_for(recipe: Recipe) -> bm.RecipeStats:
    return bm.calculate(_calc_input(recipe).to_domain())


def to_out(db: Session, recipe: Recipe) -> RecipeOut:
    stats = stats_for(recipe)
    values = {"og": stats.og, "fg": stats.fg, "abv": stats.abv, "ibu": stats.ibu, "srm": stats.srm}
    specs = calc_service.style_specs(list(style_repo.all_with_ranges(db)))
    target_slug = recipe.target_style.slug if recipe.target_style else None
    matches = rank_styles(values, specs, target_slug=target_slug)
    return RecipeOut(
        id=recipe.id,
        name=recipe.name,
        notes=recipe.notes,
        target_style=StyleSummary.from_model(recipe.target_style) if recipe.target_style else None,
        batch_volume_l=recipe.batch_volume_l,
        pre_boil_volume_l=recipe.pre_boil_volume_l,
        boil_time_min=recipe.boil_time_min,
        brewhouse_efficiency_pct=recipe.brewhouse_efficiency_pct,
        steep_efficiency_pct=recipe.steep_efficiency_pct,
        fermentables=[RecipeFermentableOut.model_validate(f) for f in recipe.fermentables],
        hops=[RecipeHopOut.model_validate(h) for h in recipe.hops],
        yeasts=[RecipeYeastOut.model_validate(y) for y in recipe.yeasts],
        created_at=recipe.created_at,
        updated_at=recipe.updated_at,
        stats=RecipeStatsOut.from_domain(stats),
        style_matches=[StyleMatchOut.from_domain(m) for m in matches],
        calc_notes=calc_service.notes_for(stats),
    )


def to_summary(recipe: Recipe) -> RecipeSummary:
    stats = stats_for(recipe)
    return RecipeSummary(
        id=recipe.id,
        name=recipe.name,
        target_style=StyleSummary.from_model(recipe.target_style) if recipe.target_style else None,
        og=stats.og,
        fg=stats.fg,
        abv=stats.abv,
        ibu=stats.ibu,
        srm=stats.srm,
        updated_at=recipe.updated_at,
    )


def list_recipes(db: Session, user: User, *, cursor: str | None, limit: int) -> Page[RecipeSummary]:
    after: tuple[datetime, uuid.UUID] | None = None
    if cursor:
        raw_ts, raw_id = decode_cursor(cursor, 2)
        try:
            after = (datetime.fromisoformat(str(raw_ts)), uuid.UUID(str(raw_id)))
        except ValueError:
            raise HTTPException(
                HTTPStatus.UNPROCESSABLE_CONTENT, detail="Invalid cursor."
            ) from None
    rows = recipe_repo.list_for_user(db, user.id, after=after, limit=limit)
    has_more = len(rows) > limit
    rows = rows[:limit]
    next_cursor = (
        encode_cursor(rows[-1].updated_at.isoformat(), rows[-1].id) if has_more and rows else None
    )
    return Page(items=[to_summary(r) for r in rows], next_cursor=next_cursor)


def _validation_problem(errors: list[FieldError]) -> ValidationProblemError:
    return ValidationProblemError(errors)


def _resolve_style(db: Session, slug: str | None) -> Style | None:
    if slug is None:
        return None
    style = db.scalars(select(Style).where(Style.slug == slug)).one_or_none()
    if style is None:
        raise _validation_problem(
            [FieldError(loc=["body", "target_style"], msg="unknown style", type="value_error")]
        )
    return style


def _check_catalog_references(db: Session, user: User, body: RecipeWrite) -> None:
    """Every referenced catalog row must be built-in or belong to the caller."""
    errors: list[FieldError] = []
    checks: list[tuple[str, str, Any, uuid.UUID | None]] = []
    for i, f in enumerate(body.fermentables):
        checks.append((f"fermentables.{i}", "fermentable_id", Fermentable, f.fermentable_id))
    for i, h in enumerate(body.hops):
        checks.append((f"hops.{i}", "hop_id", Hop, h.hop_id))
    for i, y in enumerate(body.yeasts):
        checks.append((f"yeasts.{i}", "yeast_id", Yeast, y.yeast_id))
    for path, field, model, item_id in checks:
        if item_id is None:
            continue
        if catalog_repo.get_visible(db, model, user_id=user.id, item_id=item_id) is None:
            section, index = path.split(".")
            errors.append(
                FieldError(
                    loc=["body", section, int(index), field],
                    msg="unknown catalog item",
                    type="value_error",
                )
            )
    if errors:
        raise _validation_problem(errors)


def _apply(recipe: Recipe, body: RecipeWrite, style: Style | None) -> None:
    recipe.name = body.name
    recipe.notes = body.notes
    recipe.target_style = style
    recipe.batch_volume_l = body.batch_volume_l
    recipe.pre_boil_volume_l = body.pre_boil_volume_l
    recipe.boil_time_min = body.boil_time_min
    recipe.brewhouse_efficiency_pct = body.brewhouse_efficiency_pct
    recipe.steep_efficiency_pct = body.steep_efficiency_pct
    recipe.fermentables = [
        RecipeFermentable(
            user_id=recipe.user_id,
            fermentable_id=f.fermentable_id,
            name=f.name,
            type=f.type,
            addition=f.addition,
            amount_kg=f.amount_kg,
            ppg=f.ppg,
            color_lovibond=f.color_lovibond,
            sort_order=i,
        )
        for i, f in enumerate(body.fermentables)
    ]
    recipe.hops = [
        RecipeHop(
            user_id=recipe.user_id,
            hop_id=h.hop_id,
            name=h.name,
            amount_g=h.amount_g,
            alpha_pct=h.alpha_pct,
            use=h.use,
            time_min=h.time_min,
            dry_hop_days=h.dry_hop_days,
            sort_order=i,
        )
        for i, h in enumerate(body.hops)
    ]
    recipe.yeasts = [
        RecipeYeast(
            user_id=recipe.user_id,
            yeast_id=y.yeast_id,
            name=y.name,
            attenuation_pct=y.attenuation_pct,
            sort_order=i,
        )
        for i, y in enumerate(body.yeasts)
    ]


def _check_computable(body: RecipeWrite) -> None:
    # Raises RecipeOutOfRangeError (a 422 problem) for e.g. a tonne of malt in half a litre,
    # before anything is written.
    bm.calculate(body.to_domain())


def create(db: Session, settings: Settings, user: User, body: RecipeWrite) -> RecipeOut:
    if recipe_repo.count_for_user(db, user.id) >= settings.quota_recipes:
        raise HTTPException(
            HTTPStatus.CONFLICT,
            detail=f"Recipe limit reached ({settings.quota_recipes}). Delete one to add another.",
        )
    _check_computable(body)
    style = _resolve_style(db, body.target_style)
    _check_catalog_references(db, user, body)
    recipe = Recipe(user_id=user.id)
    _apply(recipe, body, style)
    recipe_repo.add(db, recipe)
    db.refresh(recipe)
    loaded = recipe_repo.get(db, user.id, recipe.id)
    assert loaded is not None  # noqa: S101  # just written in this transaction
    return to_out(db, loaded)


def get(db: Session, user: User, recipe_id: uuid.UUID) -> RecipeOut:
    recipe = recipe_repo.get(db, user.id, recipe_id)
    if recipe is None:
        raise _not_found()
    return to_out(db, recipe)


def replace(db: Session, user: User, recipe_id: uuid.UUID, body: RecipeWrite) -> RecipeOut:
    recipe = recipe_repo.get(db, user.id, recipe_id)
    if recipe is None:
        raise _not_found()
    _check_computable(body)
    style = _resolve_style(db, body.target_style)
    _check_catalog_references(db, user, body)
    _apply(recipe, body, style)
    db.flush()
    db.refresh(recipe)
    loaded = recipe_repo.get(db, user.id, recipe.id)
    assert loaded is not None  # noqa: S101
    return to_out(db, loaded)


def delete(db: Session, user: User, recipe_id: uuid.UUID) -> None:
    recipe = recipe_repo.get(db, user.id, recipe_id)
    if recipe is None:
        raise _not_found()
    recipe_repo.delete(db, recipe)


def export_rows(db: Session, user: User) -> list[dict[str, Any]]:
    """Every recipe with its rows, for the account export."""
    rows: list[dict[str, Any]] = []
    for recipe in recipe_repo.list_for_user(db, user.id, after=None, limit=10_000):
        rows.append(
            {
                "id": recipe.id,
                "name": recipe.name,
                "notes": recipe.notes,
                "target_style": recipe.target_style.slug if recipe.target_style else None,
                "batch_volume_l": recipe.batch_volume_l,
                "pre_boil_volume_l": recipe.pre_boil_volume_l,
                "boil_time_min": recipe.boil_time_min,
                "brewhouse_efficiency_pct": recipe.brewhouse_efficiency_pct,
                "steep_efficiency_pct": recipe.steep_efficiency_pct,
                "fermentables": [
                    RecipeFermentableOut.model_validate(f).model_dump() for f in recipe.fermentables
                ],
                "hops": [RecipeHopOut.model_validate(h).model_dump() for h in recipe.hops],
                "yeasts": [RecipeYeastOut.model_validate(y).model_dump() for y in recipe.yeasts],
                "created_at": recipe.created_at,
                "updated_at": recipe.updated_at,
            }
        )
    return rows
