"""Caller identity resolution for CLI commands.

Resolves the calling agent's identity via tmux pane detection only:
tmux display-message pane ID -> Agent lookup.

The HEADSPACE_AGENT_ID env var override was removed as a security hardening
measure — it was a spoofable identity assertion that allowed agents to
impersonate other agents or bypass operator-only restrictions.

This module is shared infrastructure used by CLI commands and potentially API
routes. CallerResolutionError is NOT a ChannelError subclass — caller identity
resolution is not channel-specific logic.
"""

import logging
import subprocess

import click

from ..models.agent import Agent

logger = logging.getLogger(__name__)


class CallerResolutionError(Exception):
    """Cannot identify calling agent."""


def resolve_caller_persona():
    """Resolve the caller and return (agent, persona).

    Resolution cascade:
    1. tmux pane detection — if caller is in an agent's tmux pane, return
       (agent, agent.persona).
    2. Operator fallback — if tmux resolution fails (CallerResolutionError),
       try Persona.get_operator(). Returns (None, operator_persona) so CLI
       commands work for human operators outside of agent tmux sessions.

    Prints errors to stderr and raises SystemExit(1) on failure.

    Returns:
        tuple: (agent | None, persona) — agent is None for operator callers.

    Raises:
        SystemExit: If neither strategy resolves a persona.
    """
    try:
        agent = resolve_caller()
        if not agent.persona:
            click.echo(
                "Error: Your agent has no persona assigned. "
                "Cannot perform this operation.",
                err=True,
            )
            raise SystemExit(1)
        return agent, agent.persona
    except CallerResolutionError:
        pass

    # Operator fallback — caller is not in an agent tmux pane
    from ..models.persona import Persona

    operator = Persona.get_operator()
    if operator:
        logger.debug("Caller resolved as operator (no agent tmux context)")
        return None, operator

    click.echo(
        "Error: Cannot identify caller. No agent tmux context and no operator "
        "persona configured.",
        err=True,
    )
    raise SystemExit(1)


def resolve_caller() -> Agent:
    """Resolve the calling agent via tmux pane detection.

    Uses tmux display-message to detect the current pane ID, then looks up
    the active Agent bound to that pane. This is the sole resolution strategy
    — infrastructure-verified identity that cannot be spoofed by agents.

    Returns:
        The resolved Agent instance.

    Raises:
        CallerResolutionError: If tmux pane detection fails to resolve an active agent.
    """
    # tmux pane detection
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
