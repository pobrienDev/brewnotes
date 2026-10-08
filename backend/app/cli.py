"""Operational commands run by hand or by the host's cron: `python -m app.cli --help`."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

cli = typer.Typer(no_args_is_help=True, add_completion=False)


@cli.callback()
def main() -> None:
    """BrewNotes operational commands."""


@cli.command("export-openapi")
def export_openapi(
    out: Annotated[Path, typer.Option(help="Where to write the OpenAPI document")] = Path(
        "openapi.json"
    ),
) -> None:
    """Write the OpenAPI document without starting a server or touching the database."""
    from app.config import tooling_settings
    from app.main import create_app

    app = create_app(tooling_settings())
    document = app.openapi()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
    print(f"wrote {out} ({len(document.get('paths', {}))} paths)")


# Advisory lock keys so cron never runs two copies of the same job at once.
LOCK_CLEANUP_SESSIONS = 1_001


@cli.command("cleanup-sessions")
def cleanup_sessions() -> None:
    """Delete sessions past their idle or absolute limit. Safe to run from cron daily."""
    from datetime import UTC, datetime

    from sqlalchemy import text
    from sqlalchemy.orm import Session

    from app.config import get_settings
    from app.db import create_engine_from_settings
    from app.services.auth_service import purge_expired_sessions

    settings = get_settings()
    engine = create_engine_from_settings(settings)
    try:
        with Session(engine) as db, db.begin():
            locked = db.execute(
                text("SELECT pg_try_advisory_xact_lock(:key)"), {"key": LOCK_CLEANUP_SESSIONS}
            ).scalar()
            if not locked:
                print("another cleanup-sessions run holds the lock; nothing to do")
                return
            deleted = purge_expired_sessions(db, settings, datetime.now(UTC))
        print(f"deleted {deleted} expired sessions")
    finally:
        engine.dispose()


if __name__ == "__main__":
    cli()
