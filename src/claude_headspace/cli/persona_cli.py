"""Flask CLI commands for persona management.

Provides ``flask persona register`` and ``flask persona list`` commands.
"""

import click
from flask import current_app
from flask.cli import AppGroup
from sqlalchemy.orm import selectinload

from ..database import db
from ..models.persona import Persona
from ..models.role import Role
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


@persona_cli.command("list")
@click.option("--active", is_flag=True, default=False, help="Show only active personas.")
@click.option("--role", default=None, help="Filter by role name (case-insensitive).")
def list_command(active: bool, role: str | None) -> None:
    """List all personas in a formatted table."""
    query = (
        db.session.query(Persona)
        .options(selectinload(Persona.role), selectinload(Persona.agents))
        .join(Persona.role)
    )

    if active:
        query = query.filter(Persona.status == "active")

    if role:
        query = query.filter(Role.name.ilike(role))

    # Sort by role name, then persona name alphabetically
    personas = query.order_by(Role.name.asc(), Persona.name.asc()).all()

    if not personas:
        click.echo("No personas found.")
        return

    # Build table data
    rows = []
    for p in personas:
        agent_count = len(p.agents)
        rows.append({
            "name": p.name,
            "role": p.role.name if p.role else "-",
            "slug": p.slug,
            "status": p.status,
            "agents": str(agent_count),
        })

    # Calculate column widths
    headers = {"name": "Name", "role": "Role", "slug": "Slug", "status": "Status", "agents": "Agents"}
    widths = {}
    for key, header in headers.items():
        widths[key] = max(len(header), max(len(r[key]) for r in rows))

    # Print header
    header_line = "  ".join(h.ljust(widths[k]) for k, h in headers.items())
    click.echo(header_line)
    click.echo("  ".join("-" * widths[k] for k in headers))

    # Print rows
    for row in rows:
        line = "  ".join(row[k].ljust(widths[k]) for k in headers)
        click.echo(line)

    # Summary line
    total = len(rows)
    active_count = sum(1 for r in rows if r["status"] == "active")
    archived_count = sum(1 for r in rows if r["status"] == "archived")
    click.echo(f"\n{total} persona{'s' if total != 1 else ''} ({active_count} active, {archived_count} archived)")
