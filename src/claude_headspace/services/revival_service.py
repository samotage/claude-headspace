"""Agent revival service ("Seance").

Orchestrates the revival of dead agents by creating successor agents
with matching project and persona configuration. The successor receives
a revival instruction via tmux bridge at session_start, telling it to
run `claude-headspace transcript <predecessor-id>` to recover context.

Revival reuses the existing `previous_agent_id` field on Agent. To
distinguish revival from handoff (E8-S14), we check whether the
predecessor has a Handoff record: present = handoff, absent = revival.
"""

import logging
from typing import NamedTuple

from flask import current_app

from ..database import db
from ..models.agent import Agent
from ..models.handoff import Handoff

logger = logging.getLogger(__name__)


class RevivalResult(NamedTuple):
    """Result of a revival attempt."""

    success: bool
    message: str
    error_code: str | None = None
    successor_agent_tmux_session: str | None = None


def revive_agent(dead_agent_id: int) -> RevivalResult:
    """Revive a dead agent by creating a successor with the same config.

    Validates that the agent exists, is dead (ended_at set), and has a
    project. Delegates to ``create_agent()`` with the predecessor's
    project and persona settings.

    Args:
        dead_agent_id: ID of the dead agent to revive.

    Returns:
        RevivalResult with success status and details.
    """
    agent = db.session.get(Agent, dead_agent_id)
    if not agent:
        return RevivalResult(
            success=False,
            message="Agent not found",
            error_code="not_found",
        )

    if agent.ended_at is None:
        return RevivalResult(
            success=False,
            message="Agent is still alive — cannot revive a live agent",
            error_code="still_alive",
        )

    if not agent.project_id:
        return RevivalResult(
            success=False,
            message="Agent has no project — cannot revive without a project",
            error_code="no_project",
        )

    # Determine persona slug if the predecessor had a persona
    persona_slug = None
    if agent.persona:
        persona_slug = agent.persona.slug

    # Delegate to the existing create_agent function
    from .agent_lifecycle import create_agent

    result = create_agent(
        project_id=agent.project_id,
        persona_slug=persona_slug,
        previous_agent_id=dead_agent_id,
    )

    if not result.success:
        return RevivalResult(
            success=False,
            message=f"Failed to create successor agent: {result.message}",
            error_code="creation_failed",
        )

    logger.info(
        f"REVIVAL_INITIATED: predecessor_id={dead_agent_id}, "
        f"project_id={agent.project_id}, "
        f"persona_slug={persona_slug or 'none'}, "
        f"tmux_session={result.tmux_session_name}"
    )

    return RevivalResult(
        success=True,
        message=f"Successor agent starting in tmux session '{result.tmux_session_name}'. "
        "It will receive the predecessor's transcript at session_start.",
        successor_agent_tmux_session=result.tmux_session_name,
    )


def is_revival_successor(agent: Agent) -> bool:
    """Check if an agent is a revival successor (not a handoff successor).

    Both revival and handoff set ``previous_agent_id``. The distinction
    is whether the predecessor has a Handoff record:
    - Handoff record present -> handoff successor
    - Handoff record absent -> revival successor

    Args:
        agent: The agent to check.

    Returns:
        True if the agent is a revival successor.
    """
    if not agent.previous_agent_id:
        return False

    # Check if the predecessor has a handoff record
    handoff = (
        db.session.query(Handoff)
        .filter(Handoff.agent_id == agent.previous_agent_id)
        .first()
    )

    # No handoff record on predecessor = this is a revival
    return handoff is None


def compose_revival_instruction(predecessor_id: int) -> str:
    """Compose the revival instruction message for a successor agent.

    Tells the new agent to run the transcript CLI command to recover
    the predecessor's conversation context.

    Args:
        predecessor_id: ID of the predecessor agent.

    Returns:
        The revival instruction text to inject via tmux.
    """
    return (
        f"You are a revival of a previous agent session (agent #{predecessor_id}). "
        f"To understand what the previous agent was working on and recover its context, "
        f"run the following command:\n\n"
        f"  claude-headspace transcript {predecessor_id}\n\n"
        f"Read the output carefully. It contains the full conversation history of your "
        f"predecessor. Use it to understand the project state, what was being worked on, "
        f"and any pending tasks. Then continue where the predecessor left off."
    )
