"""The data files load, are idempotent, and contain the structures the plan calls out."""

from __future__ import annotations

from sqlalchemy import Connection, func, select
from sqlalchemy.orm import Session, selectinload

from app.models import Fermentable, Hop, Style, StyleRange, Yeast
from app.services.seed_service import seed_all


def _session(connection: Connection) -> Session:
    return Session(bind=connection, join_transaction_mode="create_savepoint")


def test_reseeding_updates_in_place(seeded: None, db_connection: Connection) -> None:
    with _session(db_connection) as db:
        before_styles = db.scalar(select(func.count()).select_from(Style))
        before_ranges = db.scalar(select(func.count()).select_from(StyleRange))
        # Corrupt a range, then re-seed: the data file wins and nothing is duplicated.
        apa = db.scalars(select(Style).where(Style.slug == "american-pale-ale")).one()
        og = next(r for r in apa.ranges if r.metric == "og")
        og.max = 2.0
        db.flush()

        counts = seed_all(db)
        assert counts.styles_created == 0
        assert counts.styles_updated == before_styles == 124
        assert counts.ranges == before_ranges
        assert counts.warnings == []
        assert (counts.fermentables, counts.hops, counts.yeasts) == (53, 50, 61)

        db.expire_all()
        apa = db.scalars(select(Style).where(Style.slug == "american-pale-ale")).one()
        assert next(r for r in apa.ranges if r.metric == "og").max == 1.060
        assert db.scalar(select(func.count()).select_from(Style)) == before_styles
        assert db.scalar(select(func.count()).select_from(StyleRange)) == before_ranges
        assert db.scalar(select(func.count()).select_from(Fermentable)) == 53
        assert db.scalar(select(func.count()).select_from(Hop)) == 50
        assert db.scalar(select(func.count()).select_from(Yeast)) == 61


def test_variants_and_multi_range_styles(seeded: None, db_connection: Connection) -> None:
    with _session(db_connection) as db:
        black = db.scalars(
            select(Style)
            .where(Style.slug == "specialty-ipa-black-ipa")
            .options(selectinload(Style.parent))
        ).one()
        assert black.code is None
        assert black.parent is not None and black.parent.slug == "specialty-ipa"
        assert black.display_name == "21B Specialty IPA: Black IPA"
        assert black.parent.display_name == "21B Specialty IPA"
        assert black.parent.ranges == []

        specialty = db.scalars(
            select(Style).where(Style.slug == "specialty-ipa").options(selectinload(Style.variants))
        ).one()
        assert sorted(v.name for v in specialty.variants) == [
            "Belgian IPA",
            "Black IPA",
            "Brown IPA",
            "Brut IPA",
            "Red IPA",
            "Rye IPA",
            "White IPA",
        ]

        historical = db.scalars(select(Style).where(Style.slug == "historical-beer")).one()
        assert historical.code == "27A"
        assert len(historical.variants) == 9
        kellerbier = next(v for v in historical.variants if v.name == "Kellerbier")
        assert kellerbier.ranges == []  # "same as base style": never matched

        saison = db.scalars(select(Style).where(Style.slug == "saison")).one()
        abv = sorted((r.min, r.max, r.label) for r in saison.ranges if r.metric == "abv")
        assert abv == [(3.5, 5.0, "table"), (5.0, 7.0, "standard"), (7.0, 9.5, "super")]
        srm = sorted((r.min, r.max, r.label) for r in saison.ranges if r.metric == "srm")
        assert srm == [(5, 14, "pale"), (15, 22, "dark")]

        apa = db.scalars(select(Style).where(Style.slug == "american-pale-ale")).one()
        assert apa.display_name == "18B American Pale Ale"
        assert apa.category_name == "Pale American Ale"
        assert apa.source_url and apa.source_url.startswith(
            "https://www.bjcp.org/style/2021/18/18B/"
        )
        assert len(apa.summary) > 40
        ranges = {r.metric: (r.min, r.max) for r in apa.ranges}
        assert ranges == {
            "og": (1.045, 1.060),
            "fg": (1.010, 1.015),
            "abv": (4.5, 6.2),
            "ibu": (30, 50),
            "srm": (5, 10),
        }

        # Specialty categories whose statistics "vary with the base beer" carry no ranges.
        fruit = db.scalars(select(Style).where(Style.slug == "fruit-beer")).one()
        assert fruit.ranges == []
        with_ranges = db.scalar(select(func.count(func.distinct(StyleRange.style_id))))
        assert with_ranges == 102


def test_builtin_catalog_has_no_owner(seeded: None, db_connection: Connection) -> None:
    with _session(db_connection) as db:
        for model in (Fermentable, Hop, Yeast):
            owned = db.scalar(
                select(func.count()).select_from(model).where(model.owner_user_id.is_not(None))
            )
            assert owned == 0
        cascade = db.scalars(select(Hop).where(Hop.name == "Cascade")).one()
        assert cascade.alpha_typical_pct == 5.5
        us05 = db.scalars(select(Yeast).where(Yeast.product_code == "US-05")).one()
        assert us05.attenuation_midpoint_pct == 80
