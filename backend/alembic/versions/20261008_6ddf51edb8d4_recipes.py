"""recipes

Phase 1c: recipes with fermentable, hop and yeast rows that snapshot the values they use.
Children reference (recipe_id, user_id) so a row can never point at another user's recipe.

Revision ID: 6ddf51edb8d4
Revises: ee2af0f562ba
Create Date: 2026-10-08 10:50:09.649951+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "6ddf51edb8d4"
down_revision: str | Sequence[str] | None = "ee2af0f562ba"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "recipes",
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("target_style_id", sa.Uuid(), nullable=True),
        sa.Column("batch_volume_l", sa.Double(), nullable=False),
        sa.Column("pre_boil_volume_l", sa.Double(), nullable=True),
        sa.Column("boil_time_min", sa.Double(), nullable=False),
        sa.Column("brewhouse_efficiency_pct", sa.Double(), nullable=False),
        sa.Column("steep_efficiency_pct", sa.Double(), nullable=False),
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
            "batch_volume_l >= 0.5 AND batch_volume_l <= 2000", name=op.f("ck_recipes_batch_volume")
        ),
        sa.CheckConstraint(
            "boil_time_min >= 0 AND boil_time_min <= 360", name=op.f("ck_recipes_boil_time")
        ),
        sa.CheckConstraint(
            "brewhouse_efficiency_pct >= 20 AND brewhouse_efficiency_pct <= 100",
            name=op.f("ck_recipes_brewhouse_efficiency"),
        ),
        sa.CheckConstraint(
            "char_length(name) BETWEEN 1 AND 200", name=op.f("ck_recipes_name_length")
        ),
        sa.CheckConstraint("char_length(notes) <= 10000", name=op.f("ck_recipes_notes_length")),
        sa.CheckConstraint(
            "pre_boil_volume_l IS NULL "
            "OR (pre_boil_volume_l >= batch_volume_l AND pre_boil_volume_l <= 2500)",
            name=op.f("ck_recipes_pre_boil_volume"),
        ),
        sa.CheckConstraint(
            "steep_efficiency_pct >= 20 AND steep_efficiency_pct <= 100",
            name=op.f("ck_recipes_steep_efficiency"),
        ),
        sa.ForeignKeyConstraint(
            ["target_style_id"],
            ["styles.id"],
            name=op.f("fk_recipes_target_style_id_styles"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_recipes_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_recipes")),
        sa.UniqueConstraint("id", "user_id", name=op.f("uq_recipes_id_user_id")),
    )
    op.create_index(
        op.f("ix_recipes_target_style_id"), "recipes", ["target_style_id"], unique=False
    )
    op.create_index(
        "ix_recipes_user_id_updated_at", "recipes", ["user_id", "updated_at"], unique=False
    )
    op.create_table(
        "recipe_fermentables",
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("fermentable_id", sa.Uuid(), nullable=True),
        sa.Column("type", sa.String(length=16), nullable=False),
        sa.Column("addition", sa.String(length=16), nullable=False),
        sa.Column("amount_kg", sa.Double(), nullable=False),
        sa.Column("ppg", sa.Double(), nullable=False),
        sa.Column("color_lovibond", sa.Double(), nullable=False),
        sa.Column("recipe_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "addition IN ('mash', 'steep', 'boil', 'fermenter')",
            name=op.f("ck_recipe_fermentables_addition"),
        ),
        sa.CheckConstraint(
            "type IN ('grain', 'extract', 'sugar', 'adjunct')",
            name=op.f("ck_recipe_fermentables_type"),
        ),
        sa.CheckConstraint(
            "amount_kg > 0 AND amount_kg <= 1000", name=op.f("ck_recipe_fermentables_amount")
        ),
        sa.CheckConstraint(
            "char_length(name) BETWEEN 1 AND 200", name=op.f("ck_recipe_fermentables_name_length")
        ),
        sa.CheckConstraint(
            "color_lovibond >= 0 AND color_lovibond <= 700",
            name=op.f("ck_recipe_fermentables_color"),
        ),
        sa.CheckConstraint("ppg >= 0 AND ppg <= 50", name=op.f("ck_recipe_fermentables_ppg")),
        sa.CheckConstraint("sort_order >= 0", name=op.f("ck_recipe_fermentables_sort_order")),
        sa.ForeignKeyConstraint(
            ["fermentable_id"],
            ["fermentables.id"],
            name=op.f("fk_recipe_fermentables_fermentable_id_fermentables"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["recipe_id", "user_id"],
            ["recipes.id", "recipes.user_id"],
            name=op.f("fk_recipe_fermentables_recipe_id_user_id_recipes"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_recipe_fermentables")),
    )
    op.create_index(
        op.f("ix_recipe_fermentables_recipe_id"), "recipe_fermentables", ["recipe_id"], unique=False
    )
    op.create_table(
        "recipe_hops",
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("hop_id", sa.Uuid(), nullable=True),
        sa.Column("amount_g", sa.Double(), nullable=False),
        sa.Column("alpha_pct", sa.Double(), nullable=False),
        sa.Column("use", sa.String(length=16), nullable=False),
        sa.Column("time_min", sa.Double(), nullable=True),
        sa.Column("dry_hop_days", sa.Double(), nullable=True),
        sa.Column("recipe_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "(use IN ('boil', 'whirlpool') AND time_min IS NOT NULL AND dry_hop_days IS NULL) "
            "OR (use = 'dry_hop' AND dry_hop_days IS NOT NULL AND time_min IS NULL) "
            "OR (use = 'first_wort' AND time_min IS NULL AND dry_hop_days IS NULL)",
            name=op.f("ck_recipe_hops_fields_match_use"),
        ),
        sa.CheckConstraint(
            "use IN ('boil', 'first_wort', 'whirlpool', 'dry_hop')", name=op.f("ck_recipe_hops_use")
        ),
        sa.CheckConstraint("alpha_pct >= 0 AND alpha_pct <= 25", name=op.f("ck_recipe_hops_alpha")),
        sa.CheckConstraint(
            "amount_g > 0 AND amount_g <= 10000", name=op.f("ck_recipe_hops_amount")
        ),
        sa.CheckConstraint(
            "char_length(name) BETWEEN 1 AND 200", name=op.f("ck_recipe_hops_name_length")
        ),
        sa.CheckConstraint(
            "dry_hop_days IS NULL OR (dry_hop_days >= 0 AND dry_hop_days <= 30)",
            name=op.f("ck_recipe_hops_dry_hop_days"),
        ),
        sa.CheckConstraint("sort_order >= 0", name=op.f("ck_recipe_hops_sort_order")),
        sa.CheckConstraint(
            "time_min IS NULL OR (time_min >= 0 AND time_min <= 360)",
            name=op.f("ck_recipe_hops_time"),
        ),
        sa.ForeignKeyConstraint(
            ["hop_id"], ["hops.id"], name=op.f("fk_recipe_hops_hop_id_hops"), ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["recipe_id", "user_id"],
            ["recipes.id", "recipes.user_id"],
            name=op.f("fk_recipe_hops_recipe_id_user_id_recipes"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_recipe_hops")),
    )
    op.create_index(op.f("ix_recipe_hops_recipe_id"), "recipe_hops", ["recipe_id"], unique=False)
    op.create_table(
        "recipe_yeasts",
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("yeast_id", sa.Uuid(), nullable=True),
        sa.Column("attenuation_pct", sa.Double(), nullable=False),
        sa.Column("recipe_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "attenuation_pct >= 40 AND attenuation_pct <= 100",
            name=op.f("ck_recipe_yeasts_attenuation"),
        ),
        sa.CheckConstraint(
            "char_length(name) BETWEEN 1 AND 200", name=op.f("ck_recipe_yeasts_name_length")
        ),
        sa.CheckConstraint("sort_order >= 0", name=op.f("ck_recipe_yeasts_sort_order")),
        sa.ForeignKeyConstraint(
            ["recipe_id", "user_id"],
            ["recipes.id", "recipes.user_id"],
            name=op.f("fk_recipe_yeasts_recipe_id_user_id_recipes"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["yeast_id"],
            ["yeasts.id"],
            name=op.f("fk_recipe_yeasts_yeast_id_yeasts"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_recipe_yeasts")),
    )
    op.create_index(
        op.f("ix_recipe_yeasts_recipe_id"), "recipe_yeasts", ["recipe_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_recipe_yeasts_recipe_id"), table_name="recipe_yeasts")
    op.drop_table("recipe_yeasts")
    op.drop_index(op.f("ix_recipe_hops_recipe_id"), table_name="recipe_hops")
    op.drop_table("recipe_hops")
    op.drop_index(op.f("ix_recipe_fermentables_recipe_id"), table_name="recipe_fermentables")
    op.drop_table("recipe_fermentables")
    op.drop_index("ix_recipes_user_id_updated_at", table_name="recipes")
    op.drop_index(op.f("ix_recipes_target_style_id"), table_name="recipes")
    op.drop_table("recipes")
