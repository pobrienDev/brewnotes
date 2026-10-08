"""styles and ingredient catalog

Phase 1b: BJCP styles with per-metric ranges (several per metric where the guideline gives
them) and the fermentable, hop and yeast catalog. Null owner means built-in.

Revision ID: ee2af0f562ba
Revises: 30c06cffc0d7
Create Date: 2026-10-08 10:22:48.540028+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "ee2af0f562ba"
down_revision: str | Sequence[str] | None = "30c06cffc0d7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "styles",
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("guideline", sa.String(length=16), nullable=False),
        sa.Column("guideline_version", sa.String(length=16), nullable=False),
        sa.Column("category_code", sa.String(length=8), nullable=False),
        sa.Column("category_name", sa.String(length=200), nullable=False),
        sa.Column("code", sa.String(length=8), nullable=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("parent_id", sa.Uuid(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("source_url", sa.String(length=2000), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["parent_id"],
            ["styles.id"],
            name=op.f("fk_styles_parent_id_styles"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_styles")),
        sa.UniqueConstraint("slug", name=op.f("uq_styles_slug")),
    )
    op.create_index(op.f("ix_styles_parent_id"), "styles", ["parent_id"], unique=False)
    op.create_index(op.f("ix_styles_sort_order"), "styles", ["sort_order"], unique=False)
    op.create_table(
        "fermentables",
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("type", sa.String(length=16), nullable=False),
        sa.Column("ppg", sa.Double(), nullable=False),
        sa.Column("color_lovibond", sa.Double(), nullable=False),
        sa.Column("default_addition", sa.String(length=16), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=True),
        sa.Column("name", sa.String(length=200), nullable=False),
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
            "default_addition IN ('mash', 'steep', 'boil', 'fermenter')",
            name=op.f("ck_fermentables_default_addition"),
        ),
        sa.CheckConstraint(
            "type IN ('grain', 'extract', 'sugar', 'adjunct')", name=op.f("ck_fermentables_type")
        ),
        sa.CheckConstraint(
            "char_length(name) BETWEEN 1 AND 200", name=op.f("ck_fermentables_name_length")
        ),
        sa.CheckConstraint(
            "color_lovibond >= 0 AND color_lovibond <= 700",
            name=op.f("ck_fermentables_color_range"),
        ),
        sa.CheckConstraint("ppg >= 0 AND ppg <= 50", name=op.f("ck_fermentables_ppg_range")),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name=op.f("fk_fermentables_owner_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_fermentables")),
        sa.UniqueConstraint(
            "owner_user_id",
            "name",
            name=op.f("uq_fermentables_owner_user_id_name"),
            postgresql_nulls_not_distinct=True,
        ),
    )
    op.create_index(
        op.f("ix_fermentables_owner_user_id"), "fermentables", ["owner_user_id"], unique=False
    )
    op.create_table(
        "hops",
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("alpha_typical_pct", sa.Double(), nullable=False),
        sa.Column("origin", sa.String(length=100), nullable=True),
        sa.Column("owner_user_id", sa.Uuid(), nullable=True),
        sa.Column("name", sa.String(length=200), nullable=False),
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
            "alpha_typical_pct >= 0 AND alpha_typical_pct <= 25", name=op.f("ck_hops_alpha_range")
        ),
        sa.CheckConstraint("char_length(name) BETWEEN 1 AND 200", name=op.f("ck_hops_name_length")),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name=op.f("fk_hops_owner_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_hops")),
        sa.UniqueConstraint(
            "owner_user_id",
            "name",
            name=op.f("uq_hops_owner_user_id_name"),
            postgresql_nulls_not_distinct=True,
        ),
    )
    op.create_index(op.f("ix_hops_owner_user_id"), "hops", ["owner_user_id"], unique=False)
    op.create_table(
        "style_ranges",
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("style_id", sa.Uuid(), nullable=False),
        sa.Column("metric", sa.String(length=8), nullable=False),
        sa.Column("min", sa.Double(), nullable=False),
        sa.Column("max", sa.Double(), nullable=False),
        sa.Column("label", sa.String(length=40), nullable=True),
        sa.CheckConstraint(
            "metric IN ('og', 'fg', 'abv', 'ibu', 'srm')", name=op.f("ck_style_ranges_metric")
        ),
        sa.CheckConstraint('"min" <= "max"', name=op.f("ck_style_ranges_min_le_max")),
        sa.ForeignKeyConstraint(
            ["style_id"],
            ["styles.id"],
            name=op.f("fk_style_ranges_style_id_styles"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_style_ranges")),
        sa.UniqueConstraint(
            "style_id",
            "metric",
            "label",
            name=op.f("uq_style_ranges_style_id_metric_label"),
            postgresql_nulls_not_distinct=True,
        ),
    )
    op.create_index(op.f("ix_style_ranges_style_id"), "style_ranges", ["style_id"], unique=False)
    op.create_table(
        "yeasts",
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("lab", sa.String(length=100), nullable=False),
        sa.Column("product_code", sa.String(length=50), nullable=True),
        sa.Column("attenuation_min_pct", sa.Double(), nullable=False),
        sa.Column("attenuation_max_pct", sa.Double(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=True),
        sa.Column("name", sa.String(length=200), nullable=False),
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
            "attenuation_min_pct >= 40 AND attenuation_max_pct <= 100 "
            "AND attenuation_min_pct <= attenuation_max_pct",
            name=op.f("ck_yeasts_attenuation_range"),
        ),
        sa.CheckConstraint(
            "char_length(name) BETWEEN 1 AND 200", name=op.f("ck_yeasts_name_length")
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name=op.f("fk_yeasts_owner_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_yeasts")),
        sa.UniqueConstraint(
            "owner_user_id",
            "lab",
            "name",
            name=op.f("uq_yeasts_owner_user_id_lab_name"),
            postgresql_nulls_not_distinct=True,
        ),
    )
    op.create_index(op.f("ix_yeasts_owner_user_id"), "yeasts", ["owner_user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_yeasts_owner_user_id"), table_name="yeasts")
    op.drop_table("yeasts")
    op.drop_index(op.f("ix_style_ranges_style_id"), table_name="style_ranges")
    op.drop_table("style_ranges")
    op.drop_index(op.f("ix_hops_owner_user_id"), table_name="hops")
    op.drop_table("hops")
    op.drop_index(op.f("ix_fermentables_owner_user_id"), table_name="fermentables")
    op.drop_table("fermentables")
    op.drop_index(op.f("ix_styles_sort_order"), table_name="styles")
    op.drop_index(op.f("ix_styles_parent_id"), table_name="styles")
    op.drop_table("styles")
