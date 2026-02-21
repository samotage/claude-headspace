"""Agent lifecycle service for creating, shutting down, and monitoring agents.

Coordinates existing infrastructure (CLI launcher, tmux bridge, context parser)
to provide remote agent lifecycle management.
"""

import logging
import os
import signal
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import NamedTuple

from flask import current_app

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


def cleanup_orphaned_sessions() -> int:
    """Kill tmux sessions with `hs-` prefix that have no matching active agent.

    Compares `list_panes()` results against active agents (ended_at IS NULL)
    in the database. Sessions whose pane IDs don't belong to any active agent
    are killed.

    Should be called once during startup, after DB init and before background
    threads start.

    Returns:
        Number of orphaned sessions killed.
    """
    try:
        panes = tmux_bridge.list_panes()
    except Exception as e:
        logger.warning(f"Orphan cleanup: list_panes failed (non-fatal): {e}")
        return 0

    # Filter to hs-* sessions
    hs_panes = [p for p in panes if p.session_name.startswith("hs-")]
    if not hs_panes:
        return 0

    # Get active agent pane IDs from DB
    try:
        active_pane_ids: set[str] = set()
        agents = (
            db.session.query(Agent.tmux_pane_id)
            .filter(Agent.ended_at.is_(None), Agent.tmux_pane_id.isnot(None))
            .all()
        )
        for (pane_id,) in agents:
            active_pane_ids.add(pane_id)
    except Exception as e:
        logger.warning(f"Orphan cleanup: DB query failed (non-fatal): {e}")
        return 0

    # Find orphaned sessions (hs-* sessions whose pane IDs aren't in active agents)
    # Group by session name so we kill each session at most once
    orphaned_sessions: set[str] = set()
    for pane in hs_panes:
        if pane.pane_id not in active_pane_ids:
            orphaned_sessions.add(pane.session_name)

    killed = 0
    for session_name in orphaned_sessions:
        result = tmux_bridge.kill_session(session_name)
        if result.success:
            killed += 1
            logger.info(f"Orphan cleanup: killed session '{session_name}'")
        else:
            logger.debug(
                f"Orphan cleanup: failed to kill session '{session_name}': "
                f"{result.error_message}"
            )

    if killed:
        logger.info(f"Orphan cleanup: killed {killed} orphaned session(s)")

    return killed


def force_terminate_agent(agent_id: int) -> ShutdownResult:
    """Force-terminate an agent by killing its tmux pane's process group.

    Uses SIGTERM (not SIGKILL) to allow graceful shutdown of Claude Code
    and its child processes. This is a manual action — not called by the reaper.

    Args:
        agent_id: ID of the agent to terminate

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
            message="Agent has no tmux pane — cannot determine process group",
        )

    pane_pid = tmux_bridge.get_pane_pid(agent.tmux_pane_id)
    if pane_pid is None:
        return ShutdownResult(
            success=False,
            message=f"Could not find PID for pane {agent.tmux_pane_id}",
        )

    try:
        pgid = os.getpgid(pane_pid)
        os.killpg(pgid, signal.SIGTERM)
        logger.info(
            f"Sent SIGTERM to process group {pgid} "
            f"(agent {agent_id}, pane {agent.tmux_pane_id}, pid {pane_pid})"
        )
        return ShutdownResult(
            success=True,
            message=f"SIGTERM sent to process group {pgid}. "
            "Agent will be cleaned up by the reaper.",
        )
    except ProcessLookupError:
        return ShutdownResult(
            success=False,
            message=f"Process {pane_pid} no longer exists",
        )
    except PermissionError:
        return ShutdownResult(
            success=False,
            message=f"Permission denied killing process group for pid {pane_pid}",
        )
    except Exception as e:
        logger.warning(f"Force terminate failed for agent {agent_id}: {e}")
        return ShutdownResult(
            success=False,
            message=f"Failed to terminate: {e}",
        )


def create_agent(
    project_id: int,
    persona_slug: str | None = None,
    previous_agent_id: int | None = None,
) -> CreateResult:
    """Create a new idle Claude Code agent for a project.

    Invokes `claude-headspace start` in the project's directory via a new
    tmux session. The agent will register itself via hooks when it starts.

    Args:
        project_id: ID of the project to create an agent for
        persona_slug: Optional persona slug to associate with the agent.
            Validated against the Persona table (must exist with status "active").
        previous_agent_id: Optional ID of the previous agent for handoff
            continuity chains (consumed by E8-S14).

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

    # Validate persona slug if provided
    if persona_slug:
        from ..models.persona import Persona

        persona = Persona.query.filter_by(slug=persona_slug, status="active").first()
        if not persona:
            return CreateResult(
                success=False,
                message=f"Persona '{persona_slug}' not found or not active. "
                "Register the persona first with: flask persona register --name <name> --role <role>",
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

    session_name = f"hs-{project.slug}-{uuid.uuid4().hex[:8]}"

    # Build CLI command args
    cli_args = [cli_path, "start"]
    if persona_slug:
        cli_args.extend(["--persona", persona_slug])

    # Build environment with optional persona/previous_agent metadata
    env = os.environ.copy()
    if persona_slug:
        env["CLAUDE_HEADSPACE_PERSONA_SLUG"] = persona_slug
    if previous_agent_id is not None:
        env["CLAUDE_HEADSPACE_PREVIOUS_AGENT_ID"] = str(previous_agent_id)

    try:
        # Start claude-headspace in a new detached tmux session
        subprocess.Popen(
            [
                "tmux",
                "new-session",
                "-d",
                "-s",
                session_name,
                "-e", f"CLAUDE_HEADSPACE_TMUX_SESSION={session_name}",
                "-c",
                str(project_path),
                "--",
            ] + cli_args,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=env,
        )

        logger.info(
            f"Started agent creation: tmux session={session_name}, "
            f"project={project.name}, path={project.path}"
            f"{f', persona={persona_slug}' if persona_slug else ''}"
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

    # Send /exit via tmux send-keys — verify Enter is accepted because
    # Claude Code's autocomplete can intercept the first Enter on slash
    # commands, leaving "/exit" sitting in the input without submitting.
    # If the pane vanishes (agent exits immediately), verification sees
    # content change and returns success.
    result = tmux_bridge.send_text(
        pane_id=agent.tmux_pane_id,
        text="/exit",
        timeout=5,
        verify_enter=True,
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


def get_agent_info(agent_id: int) -> dict | None:
    """Gather comprehensive debug info for an agent.

    Returns a dict with identity, project, lifecycle, priority, headspace,
    and command history data. Returns None if agent not found.

    Args:
        agent_id: ID of the agent

    Returns:
        Dict with all agent info sections, or None
    """
    from .card_state import format_uptime, get_effective_state, is_agent_active

    agent = db.session.get(Agent, agent_id)
    if not agent:
        return None

    session_uuid_str = str(agent.session_uuid)

    # --- Identity ---
    identity = {
        "id": agent.id,
        "session_uuid": session_uuid_str,
        "session_uuid_short": session_uuid_str[:8],
        "claude_session_id": agent.claude_session_id,
        "tmux_pane_id": agent.tmux_pane_id,
        "iterm_pane_id": agent.iterm_pane_id,
        "transcript_path": agent.transcript_path,
    }

    # Live tmux lookup — match agent's pane to get session name
    tmux_session_name = None
    tmux_pane_alive = False
    try:
        panes = tmux_bridge.list_panes()
        for pane in panes:
            if pane.pane_id == agent.tmux_pane_id:
                tmux_session_name = pane.session_name
                tmux_pane_alive = True
                break
    except Exception:
        pass  # tmux not available
    identity["tmux_session_name"] = tmux_session_name
    identity["tmux_pane_alive"] = tmux_pane_alive

    # Bridge status
    bridge_available = False
    try:
        commander = current_app.extensions.get("commander_availability")
        if commander and agent.tmux_pane_id:
            bridge_available = commander.is_available(agent_id)
    except RuntimeError:
        pass
    identity["bridge_available"] = bridge_available

    # --- Project ---
    project_info = None
    if agent.project:
        p = agent.project
        project_info = {
            "id": p.id,
            "name": p.name,
            "slug": p.slug,
            "path": p.path,
            "current_branch": p.current_branch,
            "github_repo": p.github_repo,
        }

    # --- Lifecycle ---
    effective_state = get_effective_state(agent)
    state_name = effective_state if isinstance(effective_state, str) else effective_state.name

    lifecycle = {
        "started_at": agent.started_at.isoformat() if agent.started_at else None,
        "last_seen_at": agent.last_seen_at.isoformat() if agent.last_seen_at else None,
        "ended_at": agent.ended_at.isoformat() if agent.ended_at else None,
        "uptime": format_uptime(agent.started_at) if agent.started_at else None,
        "current_state": state_name,
        "is_active": is_agent_active(agent),
    }

    # --- Priority ---
    priority = {
        "score": agent.priority_score,
        "reason": agent.priority_reason,
        "updated_at": agent.priority_updated_at.isoformat() if agent.priority_updated_at else None,
    }

    # --- Headspace ---
    from ..models.headspace_snapshot import HeadspaceSnapshot

    headspace = None
    latest_snapshot = (
        db.session.query(HeadspaceSnapshot)
        .order_by(HeadspaceSnapshot.timestamp.desc())
        .first()
    )
    if latest_snapshot:
        headspace = {
            "state": latest_snapshot.state,
            "frustration_rolling_10": latest_snapshot.frustration_rolling_10,
            "frustration_rolling_30min": latest_snapshot.frustration_rolling_30min,
            "frustration_rolling_3hr": latest_snapshot.frustration_rolling_3hr,
            "is_flow_state": latest_snapshot.is_flow_state,
            "turn_rate_per_hour": latest_snapshot.turn_rate_per_hour,
            "flow_duration_minutes": latest_snapshot.flow_duration_minutes,
            "timestamp": latest_snapshot.timestamp.isoformat(),
        }

    # Collect recent frustration scores from USER turns across last 5 commands
    frustration_scores = []
    from ..models.turn import TurnActor

    commands_for_frustration = agent.commands[:5] if agent.commands else []
    for command in commands_for_frustration:
        if hasattr(command, "turns"):
            for turn in command.turns:
                if turn.actor == TurnActor.USER and turn.frustration_score is not None:
                    frustration_scores.append({
                        "score": turn.frustration_score,
                        "timestamp": turn.timestamp.isoformat(),
                    })

    # --- Commands (last 10) with turns ---
    commands_info = []
    recent_commands = agent.commands[:10] if agent.commands else []
    for command in recent_commands:
        recent_turns = command.get_recent_turns(50)
        turns_info = []
        for turn in reversed(recent_turns):  # chronological order
            text = turn.text or ""
            text_truncated = len(text) > 500
            turns_info.append({
                "id": turn.id,
                "actor": turn.actor.value,
                "intent": turn.intent.value,
                "timestamp": turn.timestamp.isoformat(),
                "text": text[:500] if text_truncated else text,
                "text_truncated": text_truncated,
                "summary": turn.summary,
                "frustration_score": turn.frustration_score,
            })

        commands_info.append({
            "id": command.id,
            "state": command.state.value,
            "instruction": command.instruction,
            "completion_summary": command.completion_summary,
            "started_at": command.started_at.isoformat() if command.started_at else None,
            "completed_at": command.completed_at.isoformat() if command.completed_at else None,
            "turn_count": len(command.turns) if hasattr(command, "turns") else 0,
            "turns": turns_info,
        })

    return {
        "identity": identity,
        "project": project_info,
        "lifecycle": lifecycle,
        "priority": priority,
        "headspace": headspace,
        "frustration_scores": frustration_scores,
        "commands": commands_info,
    }
