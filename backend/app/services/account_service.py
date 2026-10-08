"""Profile, data export and account deletion."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models import User
from app.repositories import identity_repo, session_repo, user_repo
from app.schemas.account import UserUpdate
from app.services import catalog_service, recipe_service


def update_profile(db: Session, user: User, patch: UserUpdate) -> User:
    changes = patch.model_dump(exclude_unset=True)
    if "display_name" in changes:
        user.display_name = changes["display_name"]
    if "unit_pref" in changes:
        user.unit_pref = changes["unit_pref"]
    db.flush()
    return user


def export(
    db: Session, user: User, *, current_token_hash: str | None, now: datetime
) -> dict[str, Any]:
    """Everything the app holds about this user, as plain JSON-serialisable data.

    Later phases append their own sections (batches, tastings).
    """
    return {
        "schema_version": 2,
        "exported_at": now,
        "user": {
            "id": user.id,
            "display_name": user.display_name,
            "avatar_url": user.avatar_url,
            "unit_pref": user.unit_pref,
            "created_at": user.created_at,
            "updated_at": user.updated_at,
        },
        "identities": [
            {
                "provider": identity.provider,
                "provider_subject": identity.provider_subject,
                "linked_at": identity.created_at,
                "last_login_at": identity.last_login_at,
            }
            for identity in identity_repo.list_for_user(db, user.id)
        ],
        "sessions": [
            {
                "created_at": session.created_at,
                "last_seen_at": session.last_seen_at,
                "expires_at": session.expires_at,
                "current": session.token_hash == current_token_hash,
            }
            for session in session_repo.list_for_user(db, user.id)
        ],
        "recipes": recipe_service.export_rows(db, user),
        "custom_ingredients": catalog_service.export_custom(db, user),
    }


def delete_account(db: Session, user: User) -> None:
    """Removes the user and, through ON DELETE CASCADE, everything they own."""
    user_repo.delete(db, user)
