"""Voice agent queries and data mapping. DB only."""

from datetime import datetime, timedelta, timezone

from ..database import db
from ..models.agent import Agent
from ..models.command import CommandState


def _get_active_agents():
    """Get all active agents (not ended) — matches dashboard behaviour."""
    return db.session.query(Agent).filter(Agent.ended_at.is_(None)).all()


def _get_ended_agents(hours: int = 24) -> list:
    """Get recently ended agents (last N hours), newest first."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    return (
        db.session.query(Agent)
        .filter(Agent.ended_at.isnot(None))
        .filter(Agent.ended_at >= cutoff)
        .order_by(Agent.ended_at.desc())
        .all()
    )


def _agent_to_voice_dict(agent: Agent, include_ended_fields: bool = False) -> dict:
    """Convert an agent to a voice-friendly dict."""
    from ..services.card_state import (
        get_command_completion_summary,
        get_command_instruction,
        get_command_summary,
        get_effective_state,
        get_state_info,
    )

    current_command = agent.get_current_command()
    effective_state = get_effective_state(agent)
    state_name = (
        effective_state if isinstance(effective_state, str) else effective_state.name
    )
    state_info = get_state_info(effective_state)
    awaiting = (
        current_command is not None
        and current_command.state == CommandState.AWAITING_INPUT
    )

    # Command details from card_state helpers (consistent with dashboard)
    command_instruction = get_command_instruction(
        agent, _current_command=current_command
    )
    command_summary = get_command_summary(agent, _current_command=current_command)
    command_completion_summary = get_command_completion_summary(agent)

    # Turn count for current command
    turn_count = 0
    if current_command and current_command.turns:
        turn_count = len(current_command.turns)

    # Agent identity: hero chars from session UUID (matches dashboard)
    truncated_uuid = str(agent.session_uuid)[:8] if agent.session_uuid else ""
    hero_chars = truncated_uuid[:2] if truncated_uuid else ""
    hero_trail = truncated_uuid[2:] if truncated_uuid else ""
    project_name = agent.project.name if agent.project else "unknown"
    persona_name = agent.persona.name if agent.persona else None
    persona_role = (
        agent.persona.role.name if agent.persona and agent.persona.role else None
    )

    # Time since last activity
    if agent.last_seen_at:
        elapsed = (datetime.now(timezone.utc) - agent.last_seen_at).total_seconds()
        if elapsed < 60:
            ago = f"{int(elapsed)}s ago"
        elif elapsed < 3600:
            ago = f"{int(elapsed / 60)}m ago"
        else:
            ago = f"{int(elapsed / 3600)}h ago"
    else:
        ago = "unknown"

    # Context usage (persisted by ContextPoller)
    context = None
    if agent.context_percent_used is not None:
        context = {
            "percent_used": agent.context_percent_used,
            "remaining_tokens": agent.context_remaining_tokens or "",
        }

    result = {
        "agent_id": agent.id,
        "name": agent.name,
        "hero_chars": hero_chars,
        "hero_trail": hero_trail,
        "project": project_name,
        "state": state_name,
        "state_label": state_info.get("label", state_name),
        "awaiting_input": awaiting,
        "command_instruction": command_instruction,
        "command_summary": command_summary,
        "command_completion_summary": command_completion_summary,
        "turn_count": turn_count,
        "summary": command_summary or command_instruction,
        "last_activity_ago": ago,
        "context": context,
        "tmux_session": agent.tmux_session,
        "persona_name": persona_name,
        "persona_role": persona_role,
        "started_at": agent.started_at.isoformat() if agent.started_at else None,
    }

    if include_ended_fields and agent.ended_at:
        result["ended"] = True
        result["ended_at"] = agent.ended_at.isoformat()

    return result
