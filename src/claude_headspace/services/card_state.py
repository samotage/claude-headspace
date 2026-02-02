"""Card state computation and SSE broadcast for dashboard agent cards.

Extracts shared helpers from routes/dashboard.py so they can be used
both by the Jinja template render path and by broadcast_card_refresh()
to push full card state over SSE after every DB commit.
"""

import logging
from datetime import datetime, timedelta, timezone

from flask import current_app

from ..models.agent import Agent
from ..models.task import TaskState

logger = logging.getLogger(__name__)

# Display-only state for stale PROCESSING agents (not in TaskState enum, never persisted)
TIMED_OUT = "TIMED_OUT"

# Default fallback for active timeout (used when no app context is available)
_DEFAULT_ACTIVE_TIMEOUT_MINUTES = 5


def _get_dashboard_config() -> dict:
    """Get dashboard config from the Flask app, with safe fallback for no-context."""
    try:
        config = current_app.config.get("APP_CONFIG", {})
        return config.get("dashboard", {})
    except RuntimeError:
        return {}  # No app context (unit tests without mocking)


def get_effective_state(agent: Agent) -> TaskState | str:
    """
    Get the effective display state for an agent.

    Priority:
    1. Stale PROCESSING detection (safety net for lost commits/server restarts)
    2. Model state from the database

    Args:
        agent: The agent to check

    Returns:
        TaskState for display purposes, or TIMED_OUT string for stale processing
    """
    model_state = agent.state

    # Safety net: if task is PROCESSING but agent hasn't been heard from
    # in a while, the stop hook's DB transition was likely lost (e.g. server
    # restart killed the request mid-flight). Show as TIMED_OUT (red) instead
    # of AWAITING_INPUT (amber) to distinguish genuine input requests.
    if model_state == TaskState.PROCESSING and agent.ended_at is None:
        dashboard_config = _get_dashboard_config()
        threshold = dashboard_config.get("stale_processing_seconds")
        if threshold is None:
            raise RuntimeError(
                "Missing required config: dashboard.stale_processing_seconds. "
                "Set it in config.yaml or via DASHBOARD_STALE_PROCESSING_SECONDS env var."
            )
        elapsed = (datetime.now(timezone.utc) - agent.last_seen_at).total_seconds()
        if elapsed > threshold:
            return TIMED_OUT

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
        String like "up 32h 38m"
    """
    now = datetime.now(timezone.utc)
    delta = now - started_at

    total_seconds = int(delta.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60

    if hours > 0:
        return f"up {hours}h {minutes}m"
    elif minutes > 0:
        return f"up {minutes}m"
    else:
        return "up <1m"


def _get_completed_task_summary(task) -> str:
    """
    Get summary text for a completed task.

    Priority:
    1. task.completion_summary (AI-generated task summary)
    2. Last turn's summary
    3. Last turn's text (truncated to 100 chars)
    4. "Summarising..." (async summary in progress)

    Args:
        task: A completed Task

    Returns:
        Summary text for the completed task
    """
    if task.completion_summary:
        return task.completion_summary

    if task.turns:
        last_turn = task.turns[-1]
        if last_turn.summary:
            return last_turn.summary
        if last_turn.text:
            text = last_turn.text
            if len(text) > 100:
                return text[:100] + "..."
            return text

    return "Summarising..."


def get_task_summary(agent: Agent) -> str:
    """
    Get task summary for an agent.

    When the task is AWAITING_INPUT, prefers the most recent AGENT QUESTION
    turn (the agent's question to the user) over the user's previous command.

    Otherwise prefers AI-generated summaries when available, falls back to
    raw turn text truncated to 100 chars.

    When no active task exists, checks if the most recent task is COMPLETE
    and shows its summary (with fallbacks).

    Args:
        agent: The agent

    Returns:
        Summary text, truncated turn text, or "No active task"
    """
    from ..models.turn import TurnActor, TurnIntent

    current_task = agent.get_current_task()
    if current_task is None:
        # Check if most recent task is COMPLETE (eager-loaded, ordered by started_at desc)
        if agent.tasks and agent.tasks[0].state == TaskState.COMPLETE:
            return _get_completed_task_summary(agent.tasks[0])
        return "No active task"

    # When AWAITING_INPUT, find the most recent AGENT QUESTION turn
    if current_task.state == TaskState.AWAITING_INPUT and current_task.turns:
        for turn in reversed(current_task.turns):
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
    if current_task.turns:
        for turn in reversed(current_task.turns):
            if turn.actor == TurnActor.AGENT and turn.intent == TurnIntent.QUESTION:
                continue
            if turn.summary:
                return turn.summary
            if turn.text:
                text = turn.text
                if len(text) > 100:
                    return text[:100] + "..."
                return text
        # All turns were questions — nothing relevant to show
        return ""

    return "No active task"


def get_task_instruction(agent: Agent) -> str | None:
    """
    Get the task instruction for an agent's current or most recent task.

    Falls back to the first USER COMMAND turn's raw text (truncated to 80 chars)
    when the AI-generated instruction summary isn't available yet.

    Args:
        agent: The agent

    Returns:
        Instruction text, or None if no instruction is available
    """
    from ..models.turn import TurnActor, TurnIntent

    current_task = agent.get_current_task()
    if current_task and current_task.instruction:
        return current_task.instruction

    # Check most recent task (any state) for instruction
    if agent.tasks and agent.tasks[0].instruction:
        return agent.tasks[0].instruction

    # Fall back to first USER COMMAND turn's raw text
    task = current_task or (agent.tasks[0] if agent.tasks else None)
    if task and hasattr(task, "turns") and task.turns:
        for t in task.turns:
            if t.actor == TurnActor.USER and t.intent == TurnIntent.COMMAND:
                text = (t.text or "").strip()
                if text:
                    if len(text) > 80:
                        return text[:77] + "..."
                    return text

    return None


def get_task_completion_summary(agent: Agent) -> str | None:
    """
    Get the completion summary for an agent's most recent completed task.

    Iterates agent.tasks (eager-loaded, ordered by started_at desc) to find
    the first COMPLETE task. Returns completion_summary if available, else
    falls back to the last turn's summary field.

    Args:
        agent: The agent

    Returns:
        Completion summary text, or None if not available
    """
    if not agent.tasks:
        return None

    for task in agent.tasks:
        if task.state == TaskState.COMPLETE:
            if task.completion_summary:
                return task.completion_summary
            # Fall back to last turn's summary
            if hasattr(task, "turns") and task.turns:
                last_turn = task.turns[-1]
                if last_turn.summary:
                    return last_turn.summary
            return None

    return None


def get_state_info(state: TaskState | str) -> dict:
    """
    Get display info for a task state.

    Args:
        state: The TaskState enum value or TIMED_OUT string

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
        TaskState.IDLE: {
            "color": "green",
            "bg_class": "bg-green",
            "label": "Idle - ready for task",
        },
        TaskState.COMMANDED: {
            "color": "yellow",
            "bg_class": "bg-amber",
            "label": "Command received",
        },
        TaskState.PROCESSING: {
            "color": "blue",
            "bg_class": "bg-blue",
            "label": "Processing...",
        },
        TaskState.AWAITING_INPUT: {
            "color": "orange",
            "bg_class": "bg-amber",
            "label": "Input needed",
        },
        TaskState.COMPLETE: {
            "color": "green",
            "bg_class": "bg-green",
            "label": "Task complete",
        },
    }
    return state_map.get(
        state,
        {"color": "gray", "bg_class": "bg-muted", "label": "Unknown"},
    )


def build_card_state(agent: Agent) -> dict:
    """Build the full card state dict for an agent.

    Computes the same fields as the dashboard route's inline dict,
    suitable for JSON serialisation and SSE broadcast.

    Args:
        agent: The agent to build card state for

    Returns:
        Dictionary with all card-visible fields, state serialised to string
    """
    effective_state = get_effective_state(agent)
    state_name = effective_state if isinstance(effective_state, str) else effective_state.name

    return {
        "id": agent.id,
        "session_uuid": str(agent.session_uuid)[:8],
        "is_active": is_agent_active(agent),
        "uptime": format_uptime(agent.started_at),
        "last_seen": format_last_seen(agent.last_seen_at),
        "state": state_name,
        "state_info": get_state_info(effective_state),
        "task_summary": get_task_summary(agent),
        "task_instruction": get_task_instruction(agent),
        "task_completion_summary": get_task_completion_summary(agent),
        "priority": agent.priority_score if agent.priority_score is not None else 50,
        "priority_reason": agent.priority_reason,
        "project_name": agent.project.name if agent.project else None,
        "project_id": agent.project_id,
    }


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
        logger.debug(f"Broadcast card_refresh for agent {agent.id}: {reason}")
    except Exception as e:
        logger.debug(f"card_refresh broadcast failed (non-fatal): {e}")
