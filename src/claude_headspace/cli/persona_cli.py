"""Flask CLI commands for persona management.

Provides ``flask persona register`` for end-to-end persona creation.
"""

import click
from flask import current_app
from flask.cli import AppGroup

from ..services.persona_registration import RegistrationError, register_persona

persona_cli = AppGroup("persona", help="Persona management commands.")


@persona_cli.command("register")
@click.option("--name", required=True, help="Persona name (e.g. 'Con').")
@click.option("--role", required=True, help="Role name (e.g. 'developer'). Lowercased on input.")
@click.option("--description", default=None, help="Optional persona description.")
def register_command(name: str, role: str, description: str | None) -> None:
    """Register a new persona (DB record + filesystem assets)."""
    try:
        result = register_persona(name=name, role_name=role, description=description)
    except RegistrationError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)

    click.echo(f"Persona registered successfully:")
    click.echo(f"  Slug: {result.slug}")
    click.echo(f"  ID:   {result.id}")
    click.echo(f"  Path: {result.path}")
