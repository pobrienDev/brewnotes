import pytest

from app.domain import units


def test_exact_definitions() -> None:
    assert units.lb_to_kg(1) == 0.45359237
    assert units.gal_to_l(1) == 3.785411784
    assert units.oz_to_g(1) == 28.349523125
    assert units.c_to_f(100) == 212
    assert units.f_to_c(32) == 0
    assert units.srm_to_ebc(10) == pytest.approx(19.7)
    assert units.ebc_to_srm(19.7) == pytest.approx(10.0076)


@pytest.mark.parametrize("value", [0.001, 1.0, 4.5359237, 123.456, 1000.0])
def test_round_trips(value: float) -> None:
    assert units.kg_to_lb(units.lb_to_kg(value)) == pytest.approx(value, rel=1e-12)
    assert units.l_to_gal(units.gal_to_l(value)) == pytest.approx(value, rel=1e-12)
    assert units.g_to_oz(units.oz_to_g(value)) == pytest.approx(value, rel=1e-12)
    assert units.f_to_c(units.c_to_f(value)) == pytest.approx(value, rel=1e-12)


def test_plato_approximation() -> None:
    assert units.sg_to_plato(1.040) == pytest.approx(9.96, abs=0.01)
    assert units.sg_to_plato(1.000) == 0
