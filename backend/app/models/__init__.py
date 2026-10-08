"""SQLAlchemy models. Importing this package registers every table on Base.metadata."""

from app.db import Base

__all__ = ["Base"]
