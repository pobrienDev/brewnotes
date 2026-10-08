"""SQLAlchemy models. Importing this package registers every table on Base.metadata."""

from app.db import Base
from app.models.catalog import Fermentable, Hop, Style, StyleRange, Yeast
from app.models.recipe import Recipe, RecipeFermentable, RecipeHop, RecipeYeast
from app.models.user import OAuthIdentity, User, UserSession

__all__ = [
    "Base",
    "Fermentable",
    "Hop",
    "OAuthIdentity",
    "Recipe",
    "RecipeFermentable",
    "RecipeHop",
    "RecipeYeast",
    "Style",
    "StyleRange",
    "User",
    "UserSession",
    "Yeast",
]
