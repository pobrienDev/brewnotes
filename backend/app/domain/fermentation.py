"""Fermentation progress: apparent attenuation and current alcohol from gravity readings.

Pure functions over numbers already in storage units (specific gravity). The service decides
which original gravity to trust (the brewer's hydrometer reading if they recorded one,
otherwise the recipe snapshot's estimate) and which current gravity applies (a recorded final
gravity, otherwise the latest reading); this module only does the arithmetic and says what it
was given.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.domain import brewmath as bm


class GravitySource(StrEnum):
    MEASURED = "measured"  # the batch's own measured_og / measured_fg
    ESTIMATED = "estimated"  # computed from the recipe snapshot
    READING = "reading"  # the most recent logged reading


@dataclass(frozen=True, slots=True)
class FermentationProgress:
    og: float
    og_source: GravitySource
    current_sg: float | None
    current_sg_source: GravitySource | None
    apparent_attenuation_pct: float | None
    abv: float | None
    expected_fg: float
    expected_attenuation_pct: float | None


def apparent_attenuation(og: float, sg: float) -> float:
    """Share of the original extract that has fermented out, in percent.

    Negative results (a reading above the OG, which happens with an estimated OG or a
    mis-read hydrometer) are reported as 0 rather than as nonsense.
    """
    if og <= 1.0:
        raise ValueError("original gravity must exceed 1.000")
    return max(0.0, (og - sg) / (og - 1.0) * 100.0)


def current_abv(og: float, sg: float) -> float:
    """Alcohol so far, by the same formula the recipe calculator uses; never negative."""
    return max(0.0, bm.abv(og, sg))


def progress(
    *,
    measured_og: float | None,
    expected_og: float,
    expected_fg: float,
    measured_fg: float | None,
    latest_reading_sg: float | None,
) -> FermentationProgress:
    """Combine what the brewer measured with what the recipe predicts.

    A recorded final gravity wins over readings: once the brewer has called the batch done, a
    stale device reading should not change the numbers. Attenuation is only defined for an OG
    above 1.000; a batch brewed from a recipe with no fermentables gets None.
    """
    if measured_og is not None:
        og, og_source = measured_og, GravitySource.MEASURED
    else:
        og, og_source = expected_og, GravitySource.ESTIMATED

    if measured_fg is not None:
        current, current_source = measured_fg, GravitySource.MEASURED
    elif latest_reading_sg is not None:
        current, current_source = latest_reading_sg, GravitySource.READING
    else:
        current, current_source = None, None

    attenuation: float | None = None
    alcohol: float | None = None
    expected_attenuation: float | None = None
    if og > 1.0:
        expected_attenuation = apparent_attenuation(og, expected_fg) if expected_fg <= og else 0.0
        if current is not None:
            attenuation = apparent_attenuation(og, current)
            alcohol = current_abv(og, current)
    return FermentationProgress(
        og=og,
        og_source=og_source,
        current_sg=current,
        current_sg_source=current_source,
        apparent_attenuation_pct=attenuation,
        abv=alcohol,
        expected_fg=expected_fg,
        expected_attenuation_pct=expected_attenuation,
    )
