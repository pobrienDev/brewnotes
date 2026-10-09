"""breweries

Phase 3: breweries synced from Open Brewery DB (never hard-deleted; removed_at marks rows that
vanished upstream), plus optional brewery links on beers and tastings with SET NULL as a
safety net.

Revision ID: f5cb7deb1af2
Revises: ed1a0d7dac28
Create Date: 2026-10-09 01:42:54.792833+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f5cb7deb1af2"
down_revision: str | Sequence[str] | None = "ed1a0d7dac28"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "breweries",
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("obdb_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("brewery_type", sa.String(length=32), nullable=False),
        sa.Column("address_1", sa.String(length=200), nullable=True),
        sa.Column("address_2", sa.String(length=200), nullable=True),
        sa.Column("address_3", sa.String(length=200), nullable=True),
        sa.Column("city", sa.String(length=100), nullable=True),
        sa.Column("state_province", sa.String(length=100), nullable=True),
        sa.Column("postal_code", sa.String(length=20), nullable=True),
        sa.Column("country", sa.String(length=100), nullable=True),
        sa.Column("latitude", sa.Double(), nullable=True),
        sa.Column("longitude", sa.Double(), nullable=True),
        sa.Column("website_url", sa.String(length=500), nullable=True),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("removed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "synced_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.CheckConstraint(
            "(latitude IS NULL) = (longitude IS NULL)", name=op.f("ck_breweries_coordinates_pair")
        ),
        sa.CheckConstraint(
            "char_length(brewery_type) BETWEEN 1 AND 32",
            name=op.f("ck_breweries_brewery_type_length"),
        ),
        sa.CheckConstraint(
            "char_length(name) BETWEEN 1 AND 200", name=op.f("ck_breweries_name_length")
        ),
        sa.CheckConstraint(
            "latitude IS NULL OR (latitude >= -90 AND latitude <= 90)",
            name=op.f("ck_breweries_latitude"),
        ),
        sa.CheckConstraint(
            "longitude IS NULL OR (longitude >= -180 AND longitude <= 180)",
            name=op.f("ck_breweries_longitude"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_breweries")),
        sa.UniqueConstraint("obdb_id", name=op.f("uq_breweries_obdb_id")),
    )
    op.create_index(op.f("ix_breweries_brewery_type"), "breweries", ["brewery_type"], unique=False)
    op.create_index(
        "ix_breweries_latitude_longitude", "breweries", ["latitude", "longitude"], unique=False
    )
    op.add_column("beers", sa.Column("brewery_id", sa.Uuid(), nullable=True))
    op.create_index(op.f("ix_beers_brewery_id"), "beers", ["brewery_id"], unique=False)
    op.create_foreign_key(
        op.f("fk_beers_brewery_id_breweries"),
        "beers",
        "breweries",
        ["brewery_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column("tastings", sa.Column("brewery_id", sa.Uuid(), nullable=True))
    op.create_index(op.f("ix_tastings_brewery_id"), "tastings", ["brewery_id"], unique=False)
    op.create_foreign_key(
        op.f("fk_tastings_brewery_id_breweries"),
        "tastings",
        "breweries",
        ["brewery_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("fk_tastings_brewery_id_breweries"), "tastings", type_="foreignkey")
    op.drop_index(op.f("ix_tastings_brewery_id"), table_name="tastings")
    op.drop_column("tastings", "brewery_id")
    op.drop_constraint(op.f("fk_beers_brewery_id_breweries"), "beers", type_="foreignkey")
    op.drop_index(op.f("ix_beers_brewery_id"), table_name="beers")
    op.drop_column("beers", "brewery_id")
    op.drop_index("ix_breweries_latitude_longitude", table_name="breweries")
    op.drop_index(op.f("ix_breweries_brewery_type"), table_name="breweries")
    op.drop_table("breweries")
