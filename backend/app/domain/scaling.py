"""Scaling a recipe to another batch volume or brewhouse efficiency.

Stats are recomputed by the caller rather than assumed; they stay the same under linear
volume scaling, which the tests rely on. Scaling the pre-boil volume proportionally is an
approximation, because real boil-off is a rate per hour, not a share of the volume.
"""

from __future__ import annotations

from dataclasses import replace

from app.domain.brewmath import Addition, Recipe


def scale_to_volume(recipe: Recipe, new_batch_volume_l: float) -> Recipe:
    """Multiply every fermentable, hop and the pre-boil volume by new / old batch volume.
    Boil time and yeast stay the same."""
    if new_batch_volume_l <= 0 or recipe.batch_volume_l <= 0:
        raise ValueError("Batch volumes must be positive.")
    factor = new_batch_volume_l / recipe.batch_volume_l
    return replace(
        recipe,
        batch_volume_l=new_batch_volume_l,
        pre_boil_volume_l=(
            None if recipe.pre_boil_volume_l is None else recipe.pre_boil_volume_l * factor
        ),
        fermentables=tuple(replace(f, amount_kg=f.amount_kg * factor) for f in recipe.fermentables),
        hops=tuple(replace(h, amount_g=h.amount_g * factor) for h in recipe.hops),
    )


def scale_to_efficiency(recipe: Recipe, new_brewhouse_efficiency_pct: float) -> Recipe:
    """Scale only mash additions by old / new efficiency so the original gravity holds."""
    if new_brewhouse_efficiency_pct <= 0 or recipe.brewhouse_efficiency_pct <= 0:
        raise ValueError("Efficiencies must be positive.")
    factor = recipe.brewhouse_efficiency_pct / new_brewhouse_efficiency_pct
    return replace(
        recipe,
        brewhouse_efficiency_pct=new_brewhouse_efficiency_pct,
        fermentables=tuple(
            replace(f, amount_kg=f.amount_kg * factor) if f.addition is Addition.MASH else f
            for f in recipe.fermentables
        ),
    )
