"""Shared CLI utility functions.

Provides common helpers used across multiple CLI command groups
(channel_cli, msg_cli, persona_cli, etc.).
"""

import logging

import click
from flask import current_app

logger = logging.getLogger(__name__)


def get_channel_service():
    """Get the ChannelService from app extensions."""
    return current_app.extensions["channel_service"]


def reject_if_agent_context() -> None:
    """Reject the current CLI command if the caller is in an agent tmux context.

    This guard detects whether the caller is an agent by attempting tmux
    pane-to-agent resolution via caller_identity.resolve_caller(). If resolution
    succeeds, the caller IS an agent and the command is rejected — agents must
    not use mutating CLI commands to bypass system-mediated channel routing.

    If resolution fails (CallerResolutionError), the caller is NOT an agent
    (i.e. a human operator) and the command proceeds normally.

    This function should be called at the top of mutating CLI commands before
    any business logic executes.

    Raises:
        SystemExit(1): If the caller is detected as an agent.
    """
    from ..services.caller_identity import CallerResolutionError, resolve_caller

    try:
        agent = resolve_caller()
        # Resolution succeeded — caller is an agent. Reject.
        click.echo(
            "Error: This command is restricted to operators only. "
            "Agents cannot use mutating CLI commands directly.",
            err=True,
        )
        logger.warning(f"Agent {agent.id} attempted to use a restricted CLI command")
        raise SystemExit(1)
    except CallerResolutionError:
        # Resolution failed — caller is NOT an agent (operator). Proceed.
        pass


def print_table(headers: dict[str, str], rows: list[dict[str, str]]) -> None:
    """Print a formatted columnar table via click.echo.

    Args:
        headers: OrderedDict-style mapping of key -> display header.
        rows: List of dicts with the same keys as headers.
    """
    if not rows:
        return

    widths = {}
    for key, header in headers.items():
        widths[key] = max(
            len(header),
            max((len(r.get(key, "")) for r in rows), default=0),
        )

    header_line = "  ".join(h.ljust(widths[k]) for k, h in headers.items())
    click.echo(header_line)
    click.echo("  ".join("-" * widths[k] for k in headers))

    for row in rows:
        line = "  ".join(row.get(k, "").ljust(widths[k]) for k in headers)
        click.echo(line)
