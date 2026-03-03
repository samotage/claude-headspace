"""Flask CLI commands for channel management.

Provides ``flask channel`` command group with subcommands for creating,
listing, managing, and interacting with channels.

All commands resolve caller identity before delegating to ChannelService.
"""

import click
from flask import current_app
from flask.cli import AppGroup

from ..services.caller_identity import resolve_caller_persona
from ..services.channel_service import ChannelError
from .cli_utils import print_table

channel_cli = AppGroup("channel", help="Channel management commands.")


def _get_channel_service():
    """Get the ChannelService from app extensions."""
    return current_app.extensions["channel_service"]


@channel_cli.command("create")
@click.argument("name")
@click.option(
    "--type",
    "channel_type",
    required=True,
    type=click.Choice(["workshop", "delegation", "review", "standup", "broadcast"]),
    help="Channel type.",
)
@click.option("--description", default=None, help="Channel description.")
@click.option("--intent", default=None, help="Intent override.")
@click.option("--org", "org_id", default=None, type=int, help="Organisation ID.")
@click.option("--project", "project_id", default=None, type=int, help="Project ID.")
@click.option("--members", default=None, help="Comma-separated persona slugs to add.")
def create_command(
    name, channel_type, description, intent, org_id, project_id, members
):
    """Create a new channel."""
    _, persona = resolve_caller_persona()

    member_slugs = None
    if members:
        member_slugs = [s.strip() for s in members.split(",") if s.strip()]

    svc = _get_channel_service()
    try:
        channel = svc.create_channel(
            creator_persona=persona,
            name=name,
            channel_type=channel_type,
            description=description,
            intent_override=intent,
            organisation_id=org_id,
            project_id=project_id,
            member_slugs=member_slugs,
        )
    except ChannelError as e:
        click.echo(str(e), err=True)
        raise SystemExit(1)

    click.echo(f"Channel created: #{channel.slug}")
    click.echo(f"  Name: {channel.name}")
    click.echo(f"  Type: {channel.channel_type.value}")
    click.echo(f"  Status: {channel.status}")
    if channel.description:
        click.echo(f"  Description: {channel.description}")


@channel_cli.command("list")
@click.option(
    "--all", "all_visible", is_flag=True, help="Show all non-archived channels."
)
@click.option(
    "--status",
    default=None,
    type=click.Choice(["pending", "active", "complete", "archived"]),
    help="Filter by status.",
)
@click.option(
    "--type",
    "channel_type",
    default=None,
    type=click.Choice(["workshop", "delegation", "review", "standup", "broadcast"]),
    help="Filter by type.",
)
def list_command(all_visible, status, channel_type):
    """List channels."""
    _, persona = resolve_caller_persona()

    svc = _get_channel_service()
    try:
        channels = svc.list_channels(
            persona=persona,
            status=status,
            channel_type=channel_type,
            all_visible=all_visible,
        )
    except ChannelError as e:
        click.echo(str(e), err=True)
        raise SystemExit(1)

    if not channels:
        click.echo("No channels found.")
        return

    # Print table
    headers = {"slug": "Slug", "name": "Name", "type": "Type", "status": "Status"}
    rows = []
    for ch in channels:
        rows.append(
            {
                "slug": ch.slug,
                "name": ch.name,
                "type": ch.channel_type.value,
                "status": ch.status,
            }
        )

    print_table(headers, rows)
    click.echo(f"\n{len(channels)} channel{'s' if len(channels) != 1 else ''}")


@channel_cli.command("show")
@click.argument("slug")
def show_command(slug):
    """Show channel details."""
    svc = _get_channel_service()
    try:
        channel = svc.get_channel(slug)
    except ChannelError as e:
        click.echo(str(e), err=True)
        raise SystemExit(1)

    click.echo(f"Channel: #{channel.slug}")
    click.echo(f"  Name: {channel.name}")
    click.echo(f"  Type: {channel.channel_type.value}")
    click.echo(f"  Status: {channel.status}")
    if channel.description:
        click.echo(f"  Description: {channel.description}")
    click.echo(f"  Created: {channel.created_at.strftime('%d %b %Y, %H:%M')}")
    if channel.completed_at:
        click.echo(f"  Completed: {channel.completed_at.strftime('%d %b %Y, %H:%M')}")
    if channel.archived_at:
        click.echo(f"  Archived: {channel.archived_at.strftime('%d %b %Y, %H:%M')}")

    # Members
    members = channel.memberships
    click.echo(f"  Members: {len(members)}")
    for m in members:
        chair_marker = " (chair)" if m.is_chair else ""
        name = m.persona.name if m.persona else "Unknown"
        click.echo(f"    - {name} [{m.status}]{chair_marker}")

    # Message count (use count query instead of loading all messages)
    from ..models.message import Message

    msg_count = Message.query.filter_by(channel_id=channel.id).count()
    click.echo(f"  Messages: {msg_count}")


@channel_cli.command("members")
@click.argument("slug")
def members_command(slug):
    """List channel members."""
    svc = _get_channel_service()
    try:
        members = svc.list_members(slug)
    except ChannelError as e:
        click.echo(str(e), err=True)
        raise SystemExit(1)

    if not members:
        click.echo("No members found.")
        return

    headers = {
        "name": "Name",
        "status": "Status",
        "chair": "Chair",
        "agent": "Agent",
        "joined": "Joined",
    }
    rows = []
    for m in members:
        name = m.persona.name if m.persona else "Unknown"
        rows.append(
            {
                "name": name,
                "status": m.status,
                "chair": "yes" if m.is_chair else "",
                "agent": f"#{m.agent_id}" if m.agent_id else "-",
                "joined": m.joined_at.strftime("%d %b %Y, %H:%M"),
            }
        )

    print_table(headers, rows)


@channel_cli.command("add")
@click.argument("slug")
@click.option("--persona", required=True, help="Persona slug to add.")
def add_command(slug, persona):
    """Add a persona to a channel."""
    _, caller_persona = resolve_caller_persona()

    svc = _get_channel_service()
    try:
        membership = svc.add_member(slug, persona, caller_persona)
    except ChannelError as e:
        click.echo(str(e), err=True)
        raise SystemExit(1)

    target_name = membership.persona.name if membership.persona else persona
    if membership.agent_id:
        click.echo(f"Added {target_name} to #{slug}.")
    else:
        click.echo(f"Added {target_name} to #{slug}. Agent spinning up...")


@channel_cli.command("leave")
@click.argument("slug")
def leave_command(slug):
    """Leave a channel."""
    _, persona = resolve_caller_persona()

    svc = _get_channel_service()
    try:
        svc.leave_channel(slug, persona)
    except ChannelError as e:
        click.echo(str(e), err=True)
        raise SystemExit(1)

    click.echo(f"Left #{slug}.")


@channel_cli.command("complete")
@click.argument("slug")
def complete_command(slug):
    """Complete a channel (chair only)."""
    _, persona = resolve_caller_persona()

    svc = _get_channel_service()
    try:
        svc.complete_channel(slug, persona)
    except ChannelError as e:
        click.echo(str(e), err=True)
        raise SystemExit(1)

    click.echo(f"Channel #{slug} completed.")


@channel_cli.command("transfer-chair")
@click.argument("slug")
@click.option(
    "--to", "target_slug", required=True, help="Persona slug of the new chair."
)
def transfer_chair_command(slug, target_slug):
    """Transfer chair role to another member."""
    _, persona = resolve_caller_persona()

    svc = _get_channel_service()
    try:
        svc.transfer_chair(slug, target_slug, persona)
    except ChannelError as e:
        click.echo(str(e), err=True)
        raise SystemExit(1)

    click.echo(f"Chair transferred to {target_slug} in #{slug}.")


@channel_cli.command("mute")
@click.argument("slug")
def mute_command(slug):
    """Mute a channel."""
    _, persona = resolve_caller_persona()

    svc = _get_channel_service()
    try:
        svc.mute_channel(slug, persona)
    except ChannelError as e:
        click.echo(str(e), err=True)
        raise SystemExit(1)

    click.echo(f"Muted #{slug}.")


@channel_cli.command("unmute")
@click.argument("slug")
def unmute_command(slug):
    """Unmute a channel."""
    _, persona = resolve_caller_persona()

    svc = _get_channel_service()
    try:
        svc.unmute_channel(slug, persona)
    except ChannelError as e:
        click.echo(str(e), err=True)
        raise SystemExit(1)

    click.echo(f"Unmuted #{slug}.")
