"""Appendix A of the project plan: the American Pale Ale used as the first brewmath fixture."""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.brewmath import Addition, Fermentable, Hop, HopUse, Recipe, Yeast
from app.domain.units import gal_to_l, lb_to_kg, oz_to_g


def appendix_a_recipe(*, pre_boil: bool = False, exact: bool = True) -> Recipe:
    """exact=True converts the imperial inputs precisely; exact=False uses the rounded metric
    figures printed in the appendix (4.536 kg, 20.82 L ...)."""
    if exact:
        kg = lb_to_kg
        batch = gal_to_l(5.5)
        pre = gal_to_l(6.5)
        hop_g = oz_to_g(1.0)
        amounts = [kg(10), kg(0.5), kg(1)]
    else:
        batch, pre, hop_g = 20.82, 24.61, 28.35
        amounts = [4.536, 0.227, 0.454]
    return Recipe(
        batch_volume_l=batch,
        pre_boil_volume_l=pre if pre_boil else None,
        boil_time_min=60,
        brewhouse_efficiency_pct=72,
        fermentables=(
            Fermentable("2-row pale malt", amounts[0], 37, 2, Addition.MASH),
            Fermentable("Munich malt", amounts[1], 35, 9, Addition.MASH),
            Fermentable("Crystal 40", amounts[2], 34, 40, Addition.MASH),
        ),
        hops=(
            Hop("Cascade", hop_g, 6.5, HopUse.BOIL, time_min=60),
            Hop("Cascade", hop_g, 6.5, HopUse.BOIL, time_min=10),
            Hop("Centennial", hop_g, 10, HopUse.BOIL, time_min=5),
        ),
        yeasts=(Yeast("US-05", 75),),
    )


@dataclass(frozen=True)
class Expected:
    gravity_units: float = 55.18
    og: float = 1.055
    fg: float = 1.014
    abv: float = 5.43
    mcu: float = 11.73
    srm: float = 8.1
    ebc: float = 15.9


@dataclass(frozen=True)
class IbuExpected:
    boil_gravity: float
    utilization: tuple[float, float, float]
    ibu: tuple[float, float, float]
    total: float
    pre_boil_gravity: float | None = None


APPENDIX_A_EXPECTED = Expected()
APPENDIX_A_IBU_NO_PRE_BOIL = IbuExpected(
    boil_gravity=1.0552,
    utilization=(0.2202, 0.0798, 0.0439),
    ibu=(19.49, 7.07, 5.98),
    total=32.5,
)
APPENDIX_A_IBU_WITH_PRE_BOIL = IbuExpected(
    pre_boil_gravity=1.0467,
    boil_gravity=1.0509,
    utilization=(0.2287, 0.0829, 0.0456),
    ibu=(20.25, 7.34, 6.21),
    total=33.8,
)
