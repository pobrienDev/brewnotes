"""batches, readings, beers and tastings

Phase 2: the brewing and tasting log. Batches freeze the recipe they were brewed from in a
JSONB snapshot and point back at it through (recipe_id, user_id), cleared with Postgres's
column-list form ON DELETE SET NULL (recipe_id). Readings, beers and tastings carry user_id
and reference their parents through composite foreign keys, so no row can belong to one user
and point at another's data. A tasting is about exactly one batch or one beer (CHECK).

Revision ID: ed1a0d7dac28
Revises: 6ddf51edb8d4
Create Date: 2026-10-09 00:51:14.426696+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "ed1a0d7dac28"
down_revision: str | Sequence[str] | None = "6ddf51edb8d4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "beers",
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("brewery_name", sa.String(length=200), nullable=True),
        sa.Column("style_id", sa.Uuid(), nullable=True),
        sa.Column("abv", sa.Double(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("abv IS NULL OR (abv >= 0 AND abv <= 100)", name=op.f("ck_beers_abv")),
        sa.CheckConstraint(
            "brewery_name IS NULL OR char_length(brewery_name) BETWEEN 1 AND 200",
            name=op.f("ck_beers_brewery_name_length"),
        ),
        sa.CheckConstraint(
            "char_length(name) BETWEEN 1 AND 200", name=op.f("ck_beers_name_length")
        ),
        sa.CheckConstraint("char_length(notes) <= 10000", name=op.f("ck_beers_notes_length")),
        sa.ForeignKeyConstraint(
            ["style_id"], ["styles.id"], name=op.f("fk_beers_style_id_styles"), ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_beers_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_beers")),
        sa.UniqueConstraint("id", "user_id", name=op.f("uq_beers_id_user_id")),
    )
    op.create_index(op.f("ix_beers_style_id"), "beers", ["style_id"], unique=False)
    op.create_index("ix_beers_user_id_name", "beers", ["user_id", "name"], unique=False)
    op.create_table(
        "batches",
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("recipe_id", sa.Uuid(), nullable=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="planned", nullable=False),
        sa.Column("brew_date", sa.Date(), nullable=True),
        sa.Column("volume_l", sa.Double(), nullable=False),
        sa.Column("measured_og", sa.Double(), nullable=True),
        sa.Column("measured_fg", sa.Double(), nullable=True),
        sa.Column("recipe_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('planned', 'fermenting', 'conditioning', 'packaged', 'done')",
            name=op.f("ck_batches_status"),
        ),
        sa.CheckConstraint(
            "char_length(name) BETWEEN 1 AND 200", name=op.f("ck_batches_name_length")
        ),
        sa.CheckConstraint("char_length(notes) <= 10000", name=op.f("ck_batches_notes_length")),
        sa.CheckConstraint(
            "measured_fg IS NULL OR (measured_fg >= 0.980 AND measured_fg <= 1.200)",
            name=op.f("ck_batches_measured_fg"),
        ),
        sa.CheckConstraint(
            "measured_og IS NULL OR (measured_og >= 0.980 AND measured_og <= 1.200)",
            name=op.f("ck_batches_measured_og"),
        ),
        sa.CheckConstraint("volume_l >= 0.5 AND volume_l <= 2000", name=op.f("ck_batches_volume")),
        sa.ForeignKeyConstraint(
            ["recipe_id", "user_id"],
            ["recipes.id", "recipes.user_id"],
            name=op.f("fk_batches_recipe_id_user_id_recipes"),
            ondelete="SET NULL (recipe_id)",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_batches_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_batches")),
        sa.UniqueConstraint("id", "user_id", name=op.f("uq_batches_id_user_id")),
    )
    op.create_index(op.f("ix_batches_recipe_id"), "batches", ["recipe_id"], unique=False)
    op.create_index(
        "ix_batches_user_id_updated_at", "batches", ["user_id", "updated_at"], unique=False
    )
    op.create_table(
        "readings",
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("batch_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("taken_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("gravity_sg", sa.Double(), nullable=True),
        sa.Column("temp_c", sa.Double(), nullable=True),
        sa.Column("source", sa.String(length=16), server_default="manual", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("source IN ('manual', 'device')", name=op.f("ck_readings_source")),
        sa.CheckConstraint(
            "gravity_sg IS NOT NULL OR temp_c IS NOT NULL", name=op.f("ck_readings_has_a_value")
        ),
        sa.CheckConstraint(
            "gravity_sg IS NULL OR (gravity_sg >= 0.980 AND gravity_sg <= 1.200)",
            name=op.f("ck_readings_gravity"),
        ),
        sa.CheckConstraint(
            "temp_c IS NULL OR (temp_c >= -10 AND temp_c <= 110)", name=op.f("ck_readings_temp")
        ),
        sa.ForeignKeyConstraint(
            ["batch_id", "user_id"],
            ["batches.id", "batches.user_id"],
            name=op.f("fk_readings_batch_id_user_id_batches"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_readings")),
    )
    op.create_index(
        "ix_readings_batch_id_taken_at", "readings", ["batch_id", "taken_at"], unique=False
    )
    op.create_table(
        "tastings",
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("batch_id", sa.Uuid(), nullable=True),
        sa.Column("beer_id", sa.Uuid(), nullable=True),
        sa.Column("rating", sa.Double(), nullable=False),
        sa.Column("aroma", sa.Text(), nullable=False),
        sa.Column("appearance", sa.Text(), nullable=False),
        sa.Column("flavor", sa.Text(), nullable=False),
        sa.Column("mouthfeel", sa.Text(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column(
            "tasted_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(batch_id IS NULL) <> (beer_id IS NULL)", name=op.f("ck_tastings_exactly_one_subject")
        ),
        sa.CheckConstraint(
            "char_length(appearance) <= 2000", name=op.f("ck_tastings_appearance_length")
        ),
        sa.CheckConstraint("char_length(aroma) <= 2000", name=op.f("ck_tastings_aroma_length")),
        sa.CheckConstraint("char_length(flavor) <= 2000", name=op.f("ck_tastings_flavor_length")),
        sa.CheckConstraint(
            "char_length(mouthfeel) <= 2000", name=op.f("ck_tastings_mouthfeel_length")
        ),
        sa.CheckConstraint("char_length(notes) <= 10000", name=op.f("ck_tastings_notes_length")),
        sa.CheckConstraint(
            "rating >= 0.5 AND rating <= 5 AND rating * 2 = floor(rating * 2)",
            name=op.f("ck_tastings_rating"),
        ),
        sa.ForeignKeyConstraint(
            ["batch_id", "user_id"],
            ["batches.id", "batches.user_id"],
            name=op.f("fk_tastings_batch_id_user_id_batches"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["beer_id", "user_id"],
            ["beers.id", "beers.user_id"],
            name=op.f("fk_tastings_beer_id_user_id_beers"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_tastings_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tastings")),
    )
    op.create_index(op.f("ix_tastings_batch_id"), "tastings", ["batch_id"], unique=False)
    op.create_index(op.f("ix_tastings_beer_id"), "tastings", ["beer_id"], unique=False)
    op.create_index(
        "ix_tastings_user_id_tasted_at", "tastings", ["user_id", "tasted_at"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_tastings_user_id_tasted_at", table_name="tastings")
    op.drop_index(op.f("ix_tastings_beer_id"), table_name="tastings")
    op.drop_index(op.f("ix_tastings_batch_id"), table_name="tastings")
    op.drop_table("tastings")
    op.drop_index("ix_readings_batch_id_taken_at", table_name="readings")
    op.drop_table("readings")
    op.drop_index("ix_batches_user_id_updated_at", table_name="batches")
    op.drop_index(op.f("ix_batches_recipe_id"), table_name="batches")
    op.drop_table("batches")
    op.drop_index("ix_beers_user_id_name", table_name="beers")
    op.drop_index(op.f("ix_beers_style_id"), table_name="beers")
    op.drop_table("beers")
