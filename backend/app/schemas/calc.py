"""Responses of the stateless calculator."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from app.domain import brewmath as bm
from app.domain import style_match as sm
from app.schemas.base import Schema
from app.schemas.recipe import HopUseName, RecipeInput

MetricName = Literal["og", "fg", "abv", "ibu", "srm"]


class HopContributionOut(Schema):
    name: str
    use: HopUseName
    minutes: float
    utilization: float
    ibu: float
    estimated: bool = Field(
        description="True for whirlpool additions, which have no consensus formula"
    )


class RecipeStatsOut(Schema):
    gravity_units: float
    og: float
    fg: float
    abv: float
    abv_alternate: float | None = Field(description="Reported when OG > 1.070")
    attenuation_pct: float
    attenuation_assumed: bool
    mcu: float
    srm: float
    ebc: float
    ibu: float
    boil_gravity: float
    boil_gravity_mode: Literal["og", "average_of_pre_boil_and_og"]
    hop_contributions: list[HopContributionOut]

    @classmethod
    def from_domain(cls, stats: bm.RecipeStats) -> RecipeStatsOut:
        return cls(
            gravity_units=stats.gravity_units,
            og=stats.og,
            fg=stats.fg,
            abv=stats.abv,
            abv_alternate=stats.abv_alternate,
            attenuation_pct=stats.attenuation_pct,
            attenuation_assumed=stats.attenuation_assumed,
            mcu=stats.mcu,
            srm=stats.srm,
            ebc=stats.ebc,
            ibu=stats.ibu,
            boil_gravity=stats.boil_gravity,
            boil_gravity_mode=stats.boil_gravity_mode.value,
            hop_contributions=[
                HopContributionOut(
                    name=c.name,
                    use=c.use.value,
                    minutes=c.minutes,
                    utilization=c.utilization,
                    ibu=c.ibu,
                    estimated=c.estimated,
                )
                for c in stats.hop_contributions
            ],
        )


class RangeOut(Schema):
    min: float
    max: float
    label: str | None


class MetricMatchOut(Schema):
    metric: MetricName
    value: float
    ranges: list[RangeOut]
    status: Literal["in", "low", "high"]
    delta: float = Field(description="Signed distance from the nearest range edge; 0 when in")
    penalty: float


class StyleMatchOut(Schema):
    slug: str
    code: str | None
    display_name: str
    fits: bool
    compared: int
    score: float
    tiebreak: float
    metrics: list[MetricMatchOut]

    @classmethod
    def from_domain(cls, match: sm.StyleMatch) -> StyleMatchOut:
        return cls(
            slug=match.slug,
            code=match.code,
            display_name=match.display_name,
            fits=match.fits,
            compared=match.compared,
            score=match.score,
            tiebreak=match.tiebreak,
            metrics=[
                MetricMatchOut(
                    metric=m.metric,
                    value=m.value,
                    ranges=[RangeOut(min=r.min, max=r.max, label=r.label) for r in m.ranges],
                    status=m.status,
                    delta=m.delta,
                    penalty=m.penalty,
                )
                for m in match.metrics
            ],
        )


class CalcResult(Schema):
    stats: RecipeStatsOut
    style_matches: list[StyleMatchOut]
    notes: list[str] = Field(description="Assumptions and estimates the user should know about")


class ScaleRequest(Schema):
    recipe: RecipeInput
    batch_volume_l: float | None = Field(default=None, ge=0.5, le=2000)
    brewhouse_efficiency_pct: float | None = Field(default=None, ge=20, le=100)


class ScaleResult(Schema):
    recipe: RecipeInput
    stats: RecipeStatsOut
