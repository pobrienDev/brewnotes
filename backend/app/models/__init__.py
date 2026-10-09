"""SQLAlchemy models. Importing this package registers every table on Base.metadata."""

from app.db import Base
from app.models.batch import Batch, BatchStatus, Reading, ReadingSource
from app.models.beer import Beer
from app.models.catalog import Fermentable, Hop, Style, StyleRange, Yeast
from app.models.recipe import Recipe, RecipeFermentable, RecipeHop, RecipeYeast
from app.models.tasting import Tasting
from app.models.user import OAuthIdentity, User, UserSession

__all__ = [
    "Base",
    "Batch",
    "BatchStatus",
    "Beer",
    "Fermentable",
    "Hop",
    "OAuthIdentity",
    "Reading",
    "ReadingSource",
    "Recipe",
    "RecipeFermentable",
    "RecipeHop",
    "RecipeYeast",
    "Style",
    "StyleRange",
    "Tasting",
    "User",
    "UserSession",
    "Yeast",
]
