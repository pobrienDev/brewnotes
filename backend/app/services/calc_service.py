"""The stateless calculator: stats, style matches and scaling for a recipe body."""

from __future__ import annotations

from http import HTTPStatus

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.domain import brewmath as bm
from app.domain import scaling
from app.domain.style_match import Range, StyleSpec, rank_styles
from app.models import Style
from app.repositories import style_repo
from app.schemas.calc import CalcResult, RecipeStatsOut, ScaleRequest, ScaleResult, StyleMatchOut
from app.schemas.recipe import RecipeInput


def style_specs(styles: list[Style]) -> list[StyleSpec]:
    specs: list[StyleSpec] = []
    for style in styles:
        ranges: dict[str, list[Range]] = {}
        for style_range in style.ranges:
            ranges.setdefault(style_range.metric, []).append(
                Range(style_range.min, style_range.max, style_range.label)
            )
        specs.append(
            StyleSpec(
                slug=style.slug,
                code=style.code if style.parent is None else style.parent.code,
                display_name=style.display_name,
                ranges={metric: tuple(items) for metric, items in ranges.items()},
            )
        )
    return specs


def notes_for(stats: bm.RecipeStats) -> list[str]:
    notes: list[str] = []
    if stats.attenuation_assumed:
        notes.append(
            f"No yeast given, so {stats.attenuation_pct:g}% attenuation was assumed for FG and ABV."
        )
    if stats.boil_gravity_mode is bm.BoilGravityMode.AVERAGE:
        notes.append(
            "Hop utilisation uses the average of the pre-boil gravity and the original gravity."
        )
    else:
        notes.append(
            "Hop utilisation uses the original gravity; add a pre-boil volume to refine it."
        )
    if any(c.estimated for c in stats.hop_contributions):
        notes.append(
            "Whirlpool bitterness is an estimate: there is no consensus formula for hop stand IBU."
        )
    if stats.abv_alternate is not None:
        notes.append("OG is above 1.070, so the alternate ABV formula is also reported.")
    return notes


def calculate(db: Session, recipe: RecipeInput) -> CalcResult:
    stats = bm.calculate(recipe.to_domain())
    values = {"og": stats.og, "fg": stats.fg, "abv": stats.abv, "ibu": stats.ibu, "srm": stats.srm}
    specs = style_specs(list(style_repo.all_with_ranges(db)))
    matches = rank_styles(values, specs, target_slug=recipe.target_style)
    return CalcResult(
        stats=RecipeStatsOut.from_domain(stats),
        style_matches=[StyleMatchOut.from_domain(m) for m in matches],
        notes=notes_for(stats),
    )


def scale(request: ScaleRequest) -> ScaleResult:
    if request.batch_volume_l is None and request.brewhouse_efficiency_pct is None:
        raise HTTPException(
            HTTPStatus.UNPROCESSABLE_CONTENT,
            detail="Give a new batch_volume_l, a new brewhouse_efficiency_pct, or both.",
        )
    recipe = request.recipe.to_domain()
    if request.batch_volume_l is not None:
        recipe = scaling.scale_to_volume(recipe, request.batch_volume_l)
    if request.brewhouse_efficiency_pct is not None:
        recipe = scaling.scale_to_efficiency(recipe, request.brewhouse_efficiency_pct)
    try:
        scaled = RecipeInput.from_domain(recipe, target_style=request.recipe.target_style)
    except ValidationError as exc:
        first = exc.errors()[0]
        raise HTTPException(
            HTTPStatus.UNPROCESSABLE_CONTENT,
            detail="The scaled recipe falls outside the input limits: "
            f"{'.'.join(str(p) for p in first['loc'])} {first['msg']}.",
        ) from None
    return ScaleResult(recipe=scaled, stats=RecipeStatsOut.from_domain(bm.calculate(recipe)))
