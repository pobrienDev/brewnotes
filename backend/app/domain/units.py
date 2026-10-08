"""Exact unit definitions. The frontend's display conversions use these same constants."""

from __future__ import annotations

KG_PER_LB = 0.45359237
L_PER_US_GAL = 3.785411784
G_PER_OZ = 28.349523125
EBC_PER_SRM = 1.97
SRM_PER_EBC = 0.508


def kg_to_lb(kg: float) -> float:
    return kg / KG_PER_LB


def lb_to_kg(lb: float) -> float:
    return lb * KG_PER_LB


def l_to_gal(litres: float) -> float:
    return litres / L_PER_US_GAL


def gal_to_l(gallons: float) -> float:
    return gallons * L_PER_US_GAL


def g_to_oz(grams: float) -> float:
    return grams / G_PER_OZ


def oz_to_g(ounces: float) -> float:
    return ounces * G_PER_OZ


def c_to_f(celsius: float) -> float:
    return celsius * 9 / 5 + 32


def f_to_c(fahrenheit: float) -> float:
    return (fahrenheit - 32) * 5 / 9


def sg_to_plato(sg: float) -> float:
    """Approximation for display only."""
    return 259 - 259 / sg


def srm_to_ebc(srm: float) -> float:
    return srm * EBC_PER_SRM


def ebc_to_srm(ebc: float) -> float:
    return ebc * SRM_PER_EBC
