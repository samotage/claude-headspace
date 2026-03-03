"""Flask CLI commands for channel messaging.

Provides ``flask msg`` command group with ``send`` and ``history``
subcommands.
"""

import click
from flask import current_app
from flask.cli import AppGroup

from ..services.caller_identity import resolve_caller_persona
from ..services.channel_service import ChannelError

msg_cli = AppGroup("msg", help="Channel messaging commands.")


def _get_channel_service():
    """Get the ChannelService from app extensions."""
    return current_app.extensions["channel_service"]


@msg_cli.command("send")
@click.argument("slug")
@click.argument("content")
@click.option(
    "--type",
    "message_type",
    default="message",
    type=click.Choice(["message", "delegation", "escalation"]),
    help="Message type.",
)
@click.option("--attachment", default=None, help="File path to attach.")
def send_command(slug, content, message_type, attachment):
    """Send a message to a channel."""
    agent, persona = resolve_caller_persona()

    svc = _get_channel_service()
    try:
        message = svc.send_message(
            slug=slug,
            content=content,
            persona=persona,
            agent=agent,
            message_type=message_type,
            attachment_path=attachment,
        )
    except ChannelError as e:
        click.echo(str(e), err=True)
        raise SystemExit(1) from None

    click.echo(f"Message sent to #{slug} (id={message.id}).")


@msg_cli.command("history")
@click.argument("slug")
@click.option(
    "--format",
    "output_format",
    default="envelope",
    type=click.Choice(["envelope", "yaml"]),
    help="Output format.",
)
@click.option("--limit", default=50, type=int, help="Maximum messages.")
@click.option(
    "--since", default=None, help="ISO timestamp — show messages after this time."
)
def history_command(slug, output_format, limit, since):
    """Show message history for a channel."""
    _, persona = resolve_caller_persona()

    svc = _get_channel_service()
    try:
        messages = svc.get_history(
            slug=slug,
            persona=persona,
            limit=limit,
            since=since,
        )
    except ChannelError as e:
        click.echo(str(e), err=True)
        raise SystemExit(1) from None

    if not messages:
        click.echo(f"No messages in #{slug}.")
        return

    if output_format == "yaml":
        _format_yaml(messages)
    else:
        _format_envelope(messages, slug)


def _format_envelope(messages, slug):
    """Format messages in conversational envelope format."""
    for i, msg in enumerate(messages):
        timestamp = msg.sent_at.strftime("%d %b %Y, %H:%M")

        if msg.message_type.value == "system":
            header = f"[#{slug}] SYSTEM -- {timestamp}:"
        elif msg.persona:
            if msg.agent_id:
                header = f"[#{slug}] {msg.persona.name} (agent:{msg.agent_id}) -- {timestamp}:"
            else:
                header = f"[#{slug}] {msg.persona.name} -- {timestamp}:"
        else:
            header = f"[#{slug}] Unknown -- {timestamp}:"

        click.echo(header)
        click.echo(msg.content)
        if i < len(messages) - 1:
            click.echo()  # Blank line between messages


def _format_yaml(messages):
    """Format messages as YAML output."""
    import yaml

    output = []
    for msg in messages:
        entry = {
            "id": msg.id,
            "channel_slug": msg.channel.slug if msg.channel else None,
            "persona_slug": msg.persona.slug if msg.persona else None,
            "persona_name": msg.persona.name if msg.persona else None,
            "agent_id": msg.agent_id,
            "content": msg.content,
            "message_type": msg.message_type.value,
            "sent_at": msg.sent_at.isoformat(),
        }
        output.append(entry)

    click.echo(yaml.dump(output, default_flow_style=False, sort_keys=False))
