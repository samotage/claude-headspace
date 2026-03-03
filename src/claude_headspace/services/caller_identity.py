"""Caller identity resolution for CLI commands.

Resolves the calling agent's identity via a two-strategy cascade:
1. Override: HEADSPACE_AGENT_ID env var (takes precedence when set)
2. Primary: tmux pane detection (tmux display-message pane ID -> Agent lookup)

This module is shared infrastructure used by CLI commands and potentially API
routes. CallerResolutionError is NOT a ChannelError subclass — caller identity
resolution is not channel-specific logic.
"""

import logging
import os
import subprocess

import click

from ..database import db
from ..models.agent import Agent

logger = logging.getLogger(__name__)


class CallerResolutionError(Exception):
    """Cannot identify calling agent."""


def resolve_caller_persona():
    """Resolve the calling agent and return (agent, persona).

    Convenience wrapper for CLI commands that need both the agent and
    its persona. Prints errors to stderr and raises SystemExit(1) on
    failure.

    Returns:
        tuple: (agent, persona)

    Raises:
        SystemExit: If caller cannot be resolved or has no persona.
    """
    try:
        agent = resolve_caller()
    except CallerResolutionError as e:
        click.echo(str(e), err=True)
        raise SystemExit(1) from None

    if not agent.persona:
        click.echo(
            "Error: Your agent has no persona assigned. Cannot perform this operation.",
            err=True,
        )
        raise SystemExit(1)

    return agent, agent.persona


def resolve_caller() -> Agent:
    """Resolve the calling agent via env var override or tmux pane detection.

    Strategy 1 (override): HEADSPACE_AGENT_ID env var — takes precedence when set.
    Strategy 2 (primary): tmux display-message pane detection.

    Returns:
        The resolved Agent instance.

    Raises:
        CallerResolutionError: If neither strategy resolves to an active agent.
    """
    # Strategy 1: env var override (takes precedence when set)
    agent_id_str = os.environ.get("HEADSPACE_AGENT_ID")
    if agent_id_str:
        try:
            agent_id = int(agent_id_str)
            agent = db.session.get(Agent, agent_id)
            if agent and agent.ended_at is None:
                logger.debug(
                    f"Caller resolved via HEADSPACE_AGENT_ID: agent_id={agent_id}"
                )
                return agent
        except (ValueError, TypeError):
            pass

    # Strategy 2: tmux pane detection
    try:
        result = subprocess.run(
            ["tmux", "display-message", "-p", "#{pane_id}"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            pane_id = result.stdout.strip()
            if pane_id:
                agent = Agent.query.filter_by(
                    tmux_pane_id=pane_id, ended_at=None
                ).first()
                if agent:
                    logger.debug(
                        f"Caller resolved via tmux pane: pane_id={pane_id}, "
                        f"agent_id={agent.id}"
                    )
                    return agent
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    raise CallerResolutionError(
        "Error: Cannot identify calling agent. "
        "Are you running in a Headspace-managed session?"
    )
