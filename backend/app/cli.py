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


if __name__ == "__main__":
    cli()
