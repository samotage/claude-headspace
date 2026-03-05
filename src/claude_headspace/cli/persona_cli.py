"""Flask CLI commands for persona management.

Provides ``flask persona register``, ``flask persona list``, and
``flask persona handoffs`` commands.
"""

import re

import click
from flask.cli import AppGroup
from sqlalchemy import func
from sqlalchemy.orm import selectinload

from ..database import db
from ..models.agent import Agent
from ..models.persona import Persona
from ..models.role import Role
from ..services.persona_assets import get_persona_dir
from ..services.persona_registration import RegistrationError, register_persona
from .cli_utils import print_table, reject_if_agent_context

persona_cli = AppGroup("persona", help="Persona management commands.")


@persona_cli.command("register")
@click.option("--name", required=True, help="Persona name (e.g. 'Con').")
@click.option(
    "--role", required=True, help="Role name (e.g. 'developer'). Lowercased on input."
)
@click.option("--description", default=None, help="Optional persona description.")
def register_command(name: str, role: str, description: str | None) -> None:
    """Register a new persona (DB record + filesystem assets)."""
    reject_if_agent_context()
    try:
        result = register_persona(name=name, role_name=role, description=description)
    except RegistrationError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1) from None

    click.echo("Persona registered successfully:")
    click.echo(f"  Slug: {result.slug}")
    click.echo(f"  ID:   {result.id}")
    click.echo(f"  Path: {result.path}")


@persona_cli.command("list")
@click.option(
    "--active", is_flag=True, default=False, help="Show only active personas."
)
@click.option("--role", default=None, help="Filter by role name (case-insensitive).")
def list_command(active: bool, role: str | None) -> None:
    """List all personas in a formatted table."""
    agent_count_subq = (
        db.session.query(func.count(Agent.id))
        .filter(Agent.persona_id == Persona.id)
        .correlate(Persona)
        .scalar_subquery()
    )

    query = (
        db.session.query(Persona, agent_count_subq.label("agent_count"))
        .options(selectinload(Persona.role))
        .join(Persona.role)
    )

    if active:
        query = query.filter(Persona.status == "active")

    if role:
        query = query.filter(Role.name.ilike(role))

    # Sort by role name, then persona name alphabetically
    results = query.order_by(Role.name.asc(), Persona.name.asc()).all()

    if not results:
        click.echo("No personas found.")
        return

    # Build table data
    rows = []
    for p, agent_count in results:
        rows.append(
            {
                "name": p.name,
                "role": p.role.name if p.role else "-",
                "slug": p.slug,
                "status": p.status,
                "agents": str(agent_count or 0),
            }
        )

    # Print table
    headers = {
        "name": "Name",
        "role": "Role",
        "slug": "Slug",
        "status": "Status",
        "agents": "Agents",
    }
    print_table(headers, rows)

    # Summary line
    total = len(rows)
    active_count = sum(1 for r in rows if r["status"] == "active")
    archived_count = sum(1 for r in rows if r["status"] == "archived")
    click.echo(
        f"\n{total} persona{'s' if total != 1 else ''} ({active_count} active, {archived_count} archived)"
    )


# ── Filename parsing for handoffs command ────────────────────

# New format: {YYYY-MM-DDTHH:MM:SS}_{summary-slug}_{agent-id:NNN}.md
_NEW_FORMAT_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})_(.+)_agent-id:(\d+)\.md$"
)

# Legacy format: {YYYYMMDDTHHmmss}-{NNNNNNNN}.md
_LEGACY_FORMAT_RE = re.compile(r"^(\d{8}T\d{6})-(\d+)\.md$")


def _parse_handoff_filename(filename: str) -> dict | None:
    """Parse a handoff filename into its components.

    Returns a dict with keys: timestamp, summary, agent_id, format.
    Returns None if the filename doesn't match any known format.
    """
    m = _NEW_FORMAT_RE.match(filename)
    if m:
        return {
            "timestamp": m.group(1),
            "summary": m.group(2),
            "agent_id": m.group(3),
            "format": "new",
        }

    m = _LEGACY_FORMAT_RE.match(filename)
    if m:
        raw_ts = m.group(1)  # e.g. "20260101T120000"
        # Format as ISO-ish for display: YYYY-MM-DDTHH:MM:SS
        if len(raw_ts) == 15:
            formatted_ts = (
                f"{raw_ts[0:4]}-{raw_ts[4:6]}-{raw_ts[6:8]}"
                f"T{raw_ts[9:11]}:{raw_ts[11:13]}:{raw_ts[13:15]}"
            )
        else:
            formatted_ts = raw_ts
        return {
            "timestamp": formatted_ts,
            "summary": "(legacy)",
            "agent_id": str(int(m.group(2))),  # strip leading zeros
            "format": "legacy",
        }

    return None


@persona_cli.command("handoffs")
@click.argument("slug")
@click.option(
    "--limit",
    "-n",
    default=None,
    type=int,
    help="Show only the N most recent handoffs.",
)
@click.option(
    "--paths", is_flag=True, default=False, help="Include full absolute file paths."
)
def handoffs_command(slug: str, limit: int | None, paths: bool) -> None:
    """List all handoff files for a persona (filesystem-only)."""
    # Verify persona exists
    persona = Persona.query.filter_by(slug=slug).first()
    if not persona:
        click.echo(f"Error: persona '{slug}' not found.", err=True)
        raise SystemExit(1)

    # Resolve handoff directory via persona_assets (single source of truth)
    handoff_dir = get_persona_dir(slug) / "handoffs"

    if not handoff_dir.is_dir():
        click.echo(f"No handoffs found for persona '{slug}'.")
        return

    # Collect .md files, sorted newest first by filename
    md_files = sorted(
        (f for f in handoff_dir.iterdir() if f.suffix == ".md" and f.is_file()),
        key=lambda f: f.name,
        reverse=True,
    )

    if not md_files:
        click.echo(f"No handoffs found for persona '{slug}'.")
        return

    # Apply limit
    if limit is not None and limit > 0:
        md_files = md_files[:limit]

    # Parse and build rows
    rows = []
    for f in md_files:
        parsed = _parse_handoff_filename(f.name)
        if parsed:
            row = {
                "timestamp": parsed["timestamp"],
                "summary": parsed["summary"],
                "agent_id": parsed["agent_id"],
            }
            if paths:
                row["path"] = str(f.resolve())
            rows.append(row)
        else:
            # Unknown format — show raw filename
            row = {
                "timestamp": "?",
                "summary": f.name,
                "agent_id": "?",
            }
            if paths:
                row["path"] = str(f.resolve())
            rows.append(row)

    if not rows:
        click.echo(f"No handoffs found for persona '{slug}'.")
        return

    # Print table
    headers = {"timestamp": "Timestamp", "summary": "Summary", "agent_id": "Agent"}
    if paths:
        headers["path"] = "Path"
    print_table(headers, rows)

    # Summary
    click.echo(f"\n{len(rows)} handoff{'s' if len(rows) != 1 else ''}")
