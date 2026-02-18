"""Card state computation and SSE broadcast for dashboard agent cards.

Extracts shared helpers from routes/dashboard.py so they can be used
both by the Jinja template render path and by broadcast_card_refresh()
to push full card state over SSE after every DB commit.
"""

import logging
from datetime import datetime, timedelta, timezone

from flask import current_app

from ..models.agent import Agent
from ..models.command import CommandState

logger = logging.getLogger(__name__)

# Display-only state for stale PROCESSING agents (not in CommandState enum, never persisted)
TIMED_OUT = "TIMED_OUT"

# Default fallback for active timeout (used when no app context is available)
_DEFAULT_ACTIVE_TIMEOUT_MINUTES = 5


def _get_context_config() -> dict:
    """Get context_monitor config from the Flask app, with safe fallback."""
    try:
        config = current_app.config.get("APP_CONFIG", {})
        return config.get("context_monitor", {})
    except RuntimeError:
        return {}


def _get_dashboard_config() -> dict:
    """Get dashboard config from the Flask app, with safe fallback for no-context."""
    try:
        config = current_app.config.get("APP_CONFIG", {})
        return config.get("dashboard", {})
    except RuntimeError:
        logger.debug("No app context for dashboard config, using defaults")
        return {}  # No app context (unit tests without mocking)


def get_effective_state(agent: Agent) -> CommandState | str:
    """
    Get the effective display state for an agent.

    Priority:
    1. Stale PROCESSING detection (safety net for lost commits/server restarts)
    2. Recently completed command detection (agent.state returns IDLE when
       get_current_command() filters out COMPLETE commands, but the agent should
       display as COMPLETE until a new command starts)
    3. Model state from the database

    Args:
        agent: The agent to check

    Returns:
        CommandState for display purposes, or TIMED_OUT string for stale processing
    """
    model_state = agent.state

    # Safety net: if command is PROCESSING but agent hasn't been heard from
    # in a while, the stop hook's DB transition was likely lost (e.g. server
    # restart killed the request mid-flight). Show as TIMED_OUT (red) instead
    # of AWAITING_INPUT (amber) to distinguish genuine input requests.
    if model_state == CommandState.PROCESSING and agent.ended_at is None:
        dashboard_config = _get_dashboard_config()
        threshold = dashboard_config.get("stale_processing_seconds", 600)
        elapsed = (datetime.now(timezone.utc) - agent.last_seen_at).total_seconds()
        if elapsed > threshold:
            return TIMED_OUT

    # agent.state returns IDLE when get_current_command() filters out COMPLETE
    # commands, but the most recent command may have just completed. Report COMPLETE
    # so card_refresh SSE events place the card in the correct Kanban column.
    if model_state == CommandState.IDLE and agent.commands:
        most_recent = agent.commands[0]  # ordered by started_at desc
        if most_recent.state == CommandState.COMPLETE:
            return CommandState.COMPLETE

    return model_state


def is_agent_active(agent: Agent) -> bool:
    """
    Check if an agent is active based on ended_at and last_seen_at.

    Args:
        agent: The agent to check

    Returns:
        True if active (not ended and seen within timeout), False otherwise
    """
    if agent.ended_at is not None:
        return False
    dashboard_config = _get_dashboard_config()
    timeout_minutes = dashboard_config.get(
        "active_timeout_minutes", _DEFAULT_ACTIVE_TIMEOUT_MINUTES
    )
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=timeout_minutes)
    return agent.last_seen_at >= cutoff


def format_last_seen(last_seen_at: datetime) -> str:
    """
    Format last_seen_at as time ago in words.

    Args:
        last_seen_at: When the agent was last seen

    Returns:
        String like "2m ago", "1h 5m ago", "<1m ago"
    """
    now = datetime.now(timezone.utc)
    delta = now - last_seen_at

    total_seconds = int(delta.total_seconds())
    if total_seconds < 0:
        total_seconds = 0

    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60

    if hours > 0:
        return f"{hours}h {minutes}m ago"
    elif minutes > 0:
        return f"{minutes}m ago"
    else:
        return "<1m ago"


def format_uptime(started_at: datetime) -> str:
    """
    Format uptime as human-readable duration.

    Args:
        started_at: When the agent started

    Returns:
        String like "up 13h" or "up 45m"
    """
    now = datetime.now(timezone.utc)
    delta = now - started_at

    total_seconds = int(delta.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60

    if hours > 0:
        return f"up {hours}h"
    elif minutes > 0:
        return f"up {minutes}m"
    else:
        return "up <1m"


def _get_completed_command_summary(cmd) -> str:
    """
    Get summary text for a completed command.

    Priority:
    1. cmd.completion_summary (AI-generated command summary)
    2. Last turn's summary
    3. Last turn's text (truncated to 100 chars)
    4. "Summarising..." (async summary in progress)

    Args:
        cmd: A completed Command

    Returns:
        Summary text for the completed command
    """
    if cmd.completion_summary:
        return cmd.completion_summary

    if cmd.turns:
        # Find the last non-internal turn for display
        for last_turn in reversed(cmd.turns):
            if last_turn.is_internal:
                continue
            if last_turn.summary:
                return last_turn.summary
            if last_turn.text:
                text = last_turn.text
                if len(text) > 100:
                    return text[:100] + "..."
                return text
            break

    return "Summarising..."


def get_command_summary(agent: Agent, _current_command=None) -> str:
    """
    Get command summary for an agent.

    When the command is AWAITING_INPUT, prefers the most recent AGENT QUESTION
    turn (the agent's question to the user) over the user's previous command.

    Otherwise prefers AI-generated summaries when available, falls back to
    raw turn text truncated to 100 chars.

    When no active command exists, checks if the most recent command is COMPLETE
    and shows its summary (with fallbacks).

    Args:
        agent: The agent

    Returns:
        Summary text, truncated turn text, or "No active command"
    """
    from ..models.turn import TurnActor, TurnIntent

    current_command = _current_command if _current_command is not None else agent.get_current_command()
    if current_command is None:
        # Check if most recent command is COMPLETE (eager-loaded, ordered by started_at desc)
        if agent.commands and agent.commands[0].state == CommandState.COMPLETE:
            return _get_completed_command_summary(agent.commands[0])
        return "No active command"

    # When AWAITING_INPUT, find the most recent AGENT QUESTION turn
    if current_command.state == CommandState.AWAITING_INPUT and current_command.turns:
        for turn in reversed(current_command.turns):
            if turn.is_internal:
                continue
            if turn.actor == TurnActor.AGENT and turn.intent == TurnIntent.QUESTION:
                if turn.summary:
                    return turn.summary
                if turn.text:
                    text = turn.text
                    if len(text) > 100:
                        return text[:100] + "..."
                    return text
                break

    # Default: get most recent non-question turn
    # AGENT QUESTION turns are only shown during AWAITING_INPUT (handled above);
    # once the agent resumes, the stale question should not linger on line 04.
    if current_command.turns:
        for turn in reversed(current_command.turns):
            if turn.is_internal:
                continue
            if turn.actor == TurnActor.AGENT and turn.intent == TurnIntent.QUESTION:
                continue
            if turn.summary:
                return turn.summary
            if turn.text:
                text = turn.text
                if len(text) > 100:
                    return text[:100] + "..."
                return text
        # All turns were questions or internal — nothing relevant to show
        return ""

    return "No active command"


def get_command_instruction(agent: Agent, _current_command=None) -> str | None:
    """
    Get the command instruction for an agent's current or most recent command.

    Falls back to the first USER COMMAND turn's raw text (truncated to 80 chars)
    when the AI-generated instruction summary isn't available yet.

    Args:
        agent: The agent

    Returns:
        Instruction text, or None if no instruction is available
    """
    from ..models.turn import TurnActor, TurnIntent

    current_command = _current_command if _current_command is not None else agent.get_current_command()
    if current_command and current_command.instruction:
        logger.debug(
            f"get_command_instruction: agent={agent.id}, "
            f"command={current_command.id}, state={current_command.state.value}, "
            f"instruction={current_command.instruction!r:.60}"
        )
        return current_command.instruction

    # Check most recent command (any state) for instruction
    if agent.commands and agent.commands[0].instruction:
        logger.debug(
            f"get_command_instruction: agent={agent.id}, "
            f"fallback to commands[0]={agent.commands[0].id}, "
            f"state={agent.commands[0].state.value}, "
            f"instruction={agent.commands[0].instruction!r:.60}"
        )
        return agent.commands[0].instruction

    # Debug: log why we fell through
    if current_command:
        logger.debug(
            f"get_command_instruction: agent={agent.id}, "
            f"command={current_command.id}, state={current_command.state.value}, "
            f"instruction=None (not yet generated)"
        )
    elif agent.commands:
        logger.debug(
            f"get_command_instruction: agent={agent.id}, "
            f"no current_command, commands[0]={agent.commands[0].id}, "
            f"state={agent.commands[0].state.value}, "
            f"instruction={agent.commands[0].instruction!r}"
        )
    else:
        logger.debug(
            f"get_command_instruction: agent={agent.id}, "
            f"no current_command, no commands"
        )

    # Fall back to command.full_command (set immediately at command creation)
    cmd = current_command or (agent.commands[0] if agent.commands else None)
    if cmd and cmd.full_command:
        text = cmd.full_command.strip()
        if text:
            return text[:77] + "..." if len(text) > 80 else text

    # Fall back to first USER COMMAND turn's raw text
    if cmd and hasattr(cmd, "turns") and cmd.turns:
        for t in cmd.turns:
            if t.actor == TurnActor.USER and t.intent == TurnIntent.COMMAND:
                text = (t.text or "").strip()
                if text:
                    if len(text) > 80:
                        return text[:77] + "..."
                    return text

    return None


def get_command_completion_summary(agent: Agent) -> str | None:
    """
    Get the completion summary for an agent's most recent completed command.

    Iterates agent.commands (eager-loaded, ordered by started_at desc) to find
    the first COMPLETE command. Returns completion_summary if available, else
    falls back to the last turn's summary field.

    Args:
        agent: The agent

    Returns:
        Completion summary text, or None if not available
    """
    if not agent.commands:
        return None

    for cmd in agent.commands:
        if cmd.state == CommandState.COMPLETE:
            if cmd.completion_summary:
                return cmd.completion_summary
            # Fall back to last turn's summary
            if hasattr(cmd, "turns") and cmd.turns:
                last_turn = cmd.turns[-1]
                if last_turn.summary:
                    return last_turn.summary
            return None

    return None


def get_state_info(state: CommandState | str) -> dict:
    """
    Get display info for a command state.

    Args:
        state: The CommandState enum value or TIMED_OUT string

    Returns:
        Dictionary with color and label
    """
    # Handle TIMED_OUT display-only state
    if state == TIMED_OUT:
        return {
            "color": "red",
            "bg_class": "bg-red",
            "label": "Timed out",
        }

    state_map = {
        CommandState.IDLE: {
            "color": "green",
            "bg_class": "bg-green",
            "label": "Idle - ready for command",
        },
        CommandState.COMMANDED: {
            "color": "yellow",
            "bg_class": "bg-amber",
            "label": "Command received",
        },
        CommandState.PROCESSING: {
            "color": "blue",
            "bg_class": "bg-blue",
            "label": "Processing...",
        },
        CommandState.AWAITING_INPUT: {
            "color": "orange",
            "bg_class": "bg-amber",
            "label": "Input needed",
        },
        CommandState.COMPLETE: {
            "color": "green",
            "bg_class": "bg-green",
            "label": "Command complete",
        },
    }
    return state_map.get(
        state,
        {"color": "gray", "bg_class": "bg-muted", "label": "Unknown"},
    )


def _get_command_turn_count(agent: Agent) -> int:
    """Get turn count for the agent's most recent completed command.

    Args:
        agent: The agent

    Returns:
        Number of turns in the most recent completed command, or 0
    """
    if not agent.commands:
        return 0
    for cmd in agent.commands:
        if cmd.state == CommandState.COMPLETE:
            return len(cmd.turns) if hasattr(cmd, "turns") else 0
    return 0


def _get_command_elapsed(agent: Agent) -> str | None:
    """Get elapsed time string for the agent's most recent completed command.

    Args:
        agent: The agent

    Returns:
        Elapsed time string like "2h 15m", "5m", "<1m", or None
    """
    if not agent.commands:
        return None
    for cmd in agent.commands:
        if cmd.state == CommandState.COMPLETE:
            if cmd.started_at and cmd.completed_at:
                delta = cmd.completed_at - cmd.started_at
                total_seconds = int(delta.total_seconds())
                hours = total_seconds // 3600
                minutes = (total_seconds % 3600) // 60
                if hours > 0:
                    return f"{hours}h {minutes}m"
                elif minutes > 0:
                    return f"{minutes}m"
                else:
                    return "<1m"
            return None
    return None


def _get_current_command_turn_count(agent: Agent, _current_command=None) -> int:
    """Get turn count for the agent's current or most recent command.

    Works for any command state (active or completed).

    Args:
        agent: The agent

    Returns:
        Number of turns in the current/most recent command, or 0
    """
    current_command = _current_command if _current_command is not None else agent.get_current_command()
    if current_command and hasattr(current_command, "turns"):
        return len(current_command.turns)
    # Fall back to most recent command (may be COMPLETE)
    if agent.commands:
        cmd = agent.commands[0]
        return len(cmd.turns) if hasattr(cmd, "turns") else 0
    return 0


def _get_current_command_elapsed(agent: Agent, _current_command=None) -> str | None:
    """Get elapsed time string for the agent's current or most recent command.

    For active commands, computes time since command.started_at until now.
    For completed commands, computes time from started_at to completed_at.

    Args:
        agent: The agent

    Returns:
        Elapsed time string like "2h 15m", "5m", "<1m", or None
    """
    current_command = _current_command if _current_command is not None else agent.get_current_command()
    cmd = current_command or (agent.commands[0] if agent.commands else None)
    if not cmd or not cmd.started_at:
        return None

    if cmd.completed_at:
        delta = cmd.completed_at - cmd.started_at
    else:
        delta = datetime.now(timezone.utc) - cmd.started_at

    total_seconds = int(delta.total_seconds())
    if total_seconds < 0:
        total_seconds = 0
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    if hours > 0:
        return f"{hours}h {minutes}m"
    elif minutes > 0:
        return f"{minutes}m"
    else:
        return "<1m"


def _is_permission_question(text: str | None) -> bool:
    """Check if question text looks like a permission request summary."""
    if not text or not isinstance(text, str):
        return False
    # Permission summarizer outputs like "Bash: ls /foo", "Read: src/file.py",
    # "Permission needed: Bash", "Permission: ToolName", or generic waiting text
    permission_prefixes = (
        "Bash:", "Read:", "Write:", "Edit:", "Glob:", "Grep:",
        "NotebookEdit:", "WebFetch:", "WebSearch:",
        "Permission needed:", "Permission:",
    )
    return text.startswith(permission_prefixes) or text == "Claude is waiting for your input"


def _default_permission_options(question_text: str) -> dict:
    """Build default Yes/No structured options for permission requests."""
    return {
        "questions": [{
            "question": question_text,
            "options": [
                {"label": "Yes", "description": "Allow this action"},
                {"label": "No", "description": "Deny this action"},
            ],
        }],
        "source": "card_state_fallback",
        "status": "pending",
    }


def get_question_options(agent: Agent, _current_command=None) -> dict | None:
    """Get structured AskUserQuestion options for an agent in AWAITING_INPUT state.

    Finds the most recent AGENT QUESTION turn's tool_input field, which
    contains the full AskUserQuestion structure (questions with options).
    Falls back to default Yes/No options for permission-type questions
    when no structured options were stored on the turn.

    Args:
        agent: The agent

    Returns:
        The tool_input dict if available, None otherwise
    """
    from ..models.turn import TurnActor, TurnIntent

    current_command = _current_command if _current_command is not None else agent.get_current_command()
    if not current_command or current_command.state != CommandState.AWAITING_INPUT:
        return None

    if not current_command.turns:
        return None

    for turn in reversed(current_command.turns):
        if turn.actor == TurnActor.AGENT and turn.intent == TurnIntent.QUESTION:
            if turn.tool_input:
                if turn.tool_input.get("status") == "complete":
                    continue  # answered — skip
                return turn.tool_input
            # No tool_input: check permission fallback
            if _is_permission_question(turn.text):
                return _default_permission_options(turn.text or "Permission needed")
            return None
    return None


def build_card_state(agent: Agent) -> dict:
    """Build the full card state dict for an agent.

    Computes the same fields as the dashboard route's inline dict,
    suitable for JSON serialisation and SSE broadcast.

    Args:
        agent: The agent to build card state for

    Returns:
        Dictionary with all card-visible fields, state serialised to string
    """
    # Cache current_command lookup to avoid repeated N+1 calls
    current_command = agent.get_current_command()

    effective_state = get_effective_state(agent)
    state_name = effective_state if isinstance(effective_state, str) else effective_state.name

    truncated_uuid = str(agent.session_uuid)[:8]
    card = {
        "id": agent.id,
        "session_uuid": truncated_uuid,
        "hero_chars": truncated_uuid[:2],
        "hero_trail": truncated_uuid[2:],
        "is_active": is_agent_active(agent),
        "uptime": format_uptime(agent.started_at),
        "last_seen": format_last_seen(agent.last_seen_at),
        "state": state_name,
        "state_info": get_state_info(effective_state),
        "command_summary": get_command_summary(agent, _current_command=current_command),
        "command_instruction": get_command_instruction(agent, _current_command=current_command),
        "command_completion_summary": get_command_completion_summary(agent),
        "priority": agent.priority_score if agent.priority_score is not None else 50,
        "priority_reason": agent.priority_reason,
        "project_name": agent.project.name if agent.project else None,
        "project_slug": agent.project.slug if agent.project else None,
        "project_id": agent.project_id,
        "tmux_session": agent.tmux_session,
    }

    # Plan mode label overrides (before command ID, so state_info is already in card)
    if current_command:
        if current_command.plan_content and current_command.plan_approved_at:
            card["state_info"] = {**card["state_info"], "label": "Executing plan..."}
        elif current_command.plan_content and not current_command.plan_approved_at:
            card["state_info"] = {**card["state_info"], "label": "Planning..."}
        elif current_command.plan_file_path == "pending":
            card["state_info"] = {**card["state_info"], "label": "Planning..."}

    # Plan content for frontend
    has_plan = bool(current_command and current_command.plan_content)
    card["has_plan"] = has_plan
    if has_plan:
        card["plan_content"] = current_command.plan_content

    # Include current command ID for on-demand full-text drill-down
    command_for_id = current_command or (agent.commands[0] if agent.commands else None)
    card["current_command_id"] = command_for_id.id if command_for_id else None

    # Include turn count and elapsed time for all states (used by
    # the agent card footer and condensed completed-command card)
    card["turn_count"] = _get_current_command_turn_count(agent, _current_command=current_command)
    card["elapsed"] = _get_current_command_elapsed(agent, _current_command=current_command)

    # Include structured question options for AWAITING_INPUT cards
    options = get_question_options(agent, _current_command=current_command)
    if options:
        card["question_options"] = options

    # Context usage
    card["context"] = None
    if agent.context_percent_used is not None:
        ctx_config = _get_context_config()
        card["context"] = {
            "percent_used": agent.context_percent_used,
            "remaining_tokens": agent.context_remaining_tokens or "",
            "warning_threshold": ctx_config.get("warning_threshold", 65),
            "high_threshold": ctx_config.get("high_threshold", 75),
        }

    # Bridge connectivity: cache first, live check fallback
    card["is_bridge_connected"] = False
    if agent.tmux_pane_id:
        try:
            commander = current_app.extensions.get("commander_availability")
            if commander:
                available = commander.is_available(agent.id)
                if not available:
                    available = commander.check_agent(
                        agent.id, agent.tmux_pane_id
                    )
                card["is_bridge_connected"] = available
        except RuntimeError:
            pass  # No app context (unit tests)

    return card


def broadcast_card_refresh(agent: Agent, reason: str) -> None:
    """Broadcast a card_refresh SSE event with the full card state.

    Wrapped in try/except so callers never fail due to broadcast issues.

    Args:
        agent: The agent whose card should be refreshed
        reason: Why the refresh was triggered (e.g. "session_start", "stop")
    """
    try:
        from .broadcaster import get_broadcaster

        card = build_card_state(agent)
        card["agent_id"] = agent.id  # Top-level for broadcaster filter matching
        card["reason"] = reason
        card["timestamp"] = datetime.now(timezone.utc).isoformat()

        get_broadcaster().broadcast("card_refresh", card)
        logger.debug(f"Broadcast card_refresh for agent {agent.id}: reason={reason}, instruction={card.get('command_instruction', 'N/A')!r:.60}")
    except Exception as e:
        logger.info(f"card_refresh broadcast failed (non-fatal): {e}")
