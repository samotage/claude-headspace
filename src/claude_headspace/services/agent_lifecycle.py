"""Agent lifecycle service for creating, shutting down, and monitoring agents.

Coordinates existing infrastructure (CLI launcher, tmux bridge, context parser)
to provide remote agent lifecycle management.
"""

import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import NamedTuple

from ..database import db
from ..models.agent import Agent
from ..models.project import Project
from . import tmux_bridge
from .context_parser import parse_context_usage

logger = logging.getLogger(__name__)

# Timeout for subprocess operations (seconds)
SUBPROCESS_TIMEOUT = 10


class CreateResult(NamedTuple):
    """Result of agent creation."""

    success: bool
    message: str
    tmux_session_name: str | None = None


class ShutdownResult(NamedTuple):
    """Result of agent shutdown."""

    success: bool
    message: str


class ContextResult(NamedTuple):
    """Result of context usage query."""

    available: bool
    percent_used: int | None = None
    remaining_tokens: str | None = None
    raw: str | None = None
    reason: str | None = None


def create_agent(project_id: int) -> CreateResult:
    """Create a new idle Claude Code agent for a project.

    Invokes `claude-headspace start` in the project's directory via a new
    tmux session. The agent will register itself via hooks when it starts.

    Args:
        project_id: ID of the project to create an agent for

    Returns:
        CreateResult with success status and message
    """
    project = db.session.get(Project, project_id)
    if not project:
        return CreateResult(success=False, message="Project not found")

    project_path = Path(project.path)
    if not project_path.exists():
        return CreateResult(
            success=False,
            message=f"Project path does not exist: {project.path}",
        )

    # Check that tmux is available
    if not shutil.which("tmux"):
        return CreateResult(
            success=False, message="tmux is not installed"
        )

    # Check that claude-headspace CLI is available
    cli_path = shutil.which("claude-headspace")
    if not cli_path:
        return CreateResult(
            success=False, message="claude-headspace CLI not found"
        )

    # Generate a unique tmux session name
    import uuid

    session_name = f"hs-{project.name}-{uuid.uuid4().hex[:8]}"

    try:
        # Start claude-headspace in a new detached tmux session
        subprocess.Popen(
            [
                "tmux",
                "new-session",
                "-d",
                "-s",
                session_name,
                "-c",
                str(project_path),
                "--",
                cli_path,
                "start",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=os.environ.copy(),
        )

        logger.info(
            f"Started agent creation: tmux session={session_name}, "
            f"project={project.name}, path={project.path}"
        )

        return CreateResult(
            success=True,
            message=f"Agent starting in tmux session '{session_name}'. "
            "It will appear on the dashboard when hooks fire.",
            tmux_session_name=session_name,
        )

    except Exception as e:
        logger.exception(f"Failed to create agent for project {project_id}: {e}")
        return CreateResult(success=False, message=f"Failed to start agent: {e}")


def shutdown_agent(agent_id: int) -> ShutdownResult:
    """Gracefully shut down an agent by sending /exit to its tmux pane.

    Args:
        agent_id: ID of the agent to shut down

    Returns:
        ShutdownResult with success status and message
    """
    agent = db.session.get(Agent, agent_id)
    if not agent:
        return ShutdownResult(success=False, message="Agent not found")

    if agent.ended_at is not None:
        return ShutdownResult(success=False, message="Agent is already ended")

    if not agent.tmux_pane_id:
        return ShutdownResult(
            success=False,
            message="Agent has no tmux pane — cannot send graceful shutdown",
        )

    # Send /exit via tmux send-keys
    result = tmux_bridge.send_text(
        pane_id=agent.tmux_pane_id,
        text="/exit",
        timeout=5,
    )

    if not result.success:
        error_msg = result.error_message or "Send failed"
        logger.warning(
            f"Failed to send /exit to agent {agent_id} "
            f"(pane {agent.tmux_pane_id}): {error_msg}"
        )
        return ShutdownResult(
            success=False, message=f"Failed to send /exit: {error_msg}"
        )

    logger.info(
        f"Sent /exit to agent {agent_id} (pane {agent.tmux_pane_id}). "
        "Hooks will handle cleanup."
    )

    return ShutdownResult(
        success=True,
        message="Shutdown command sent. Agent will terminate via hooks.",
    )


def get_context_usage(agent_id: int) -> ContextResult:
    """Get context window usage for an agent by reading its tmux pane.

    Args:
        agent_id: ID of the agent to query

    Returns:
        ContextResult with availability and usage data
    """
    agent = db.session.get(Agent, agent_id)
    if not agent:
        return ContextResult(available=False, reason="agent_not_found")

    if agent.ended_at is not None:
        return ContextResult(available=False, reason="agent_ended")

    if not agent.tmux_pane_id:
        return ContextResult(available=False, reason="no_tmux_pane")

    # Capture the last few lines of the pane (statusline is at the bottom)
    pane_text = tmux_bridge.capture_pane(agent.tmux_pane_id, lines=5)

    if not pane_text:
        return ContextResult(available=False, reason="capture_failed")

    ctx = parse_context_usage(pane_text)
    if not ctx:
        return ContextResult(available=False, reason="statusline_not_found")

    return ContextResult(
        available=True,
        percent_used=ctx["percent_used"],
        remaining_tokens=ctx["remaining_tokens"],
        raw=ctx["raw"],
    )
