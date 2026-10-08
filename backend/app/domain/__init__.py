"""Pure brewing logic: math, units, scaling and style matching.

Plain dataclasses in and out. No ORM, no Pydantic, no I/O. Standard brewing formulas are
imperial, so values are converted from metric storage first (see units.py).
"""
