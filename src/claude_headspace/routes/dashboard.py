"""Dashboard route for agent monitoring."""

from datetime import datetime, timedelta, timezone

from flask import Blueprint, current_app, render_template, request
from sqlalchemy.orm import selectinload

from ..database import db
from ..models import Agent, Project, Task, TaskState

dashboard_bp = Blueprint("dashboard", __name__)

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


def get_recommended_next(all_agents: list, agent_data_map: dict) -> dict | None:
    """
    Get the highest priority agent to recommend.

    Priority order:
    1. Agents with AWAITING_INPUT (oldest waiting first)
    2. Most recently active agent (by last_seen_at)

    Args:
        all_agents: List of Agent model instances
        agent_data_map: Dict mapping agent.id to processed agent data dict

    Returns:
        Dictionary with recommended agent data and rationale, or None
    """
    if not all_agents:
        return None

    # Filter to agents needing attention (AWAITING_INPUT or TIMED_OUT)
    needs_attention = [
        a for a in all_agents
        if get_effective_state(a) in (TaskState.AWAITING_INPUT, TIMED_OUT)
    ]

    if needs_attention:
        # Sort by last_seen_at ascending (oldest waiting first)
        needs_attention.sort(key=lambda a: a.last_seen_at)
        agent = needs_attention[0]
        effective = get_effective_state(agent)

        # Calculate wait time
        wait_delta = datetime.now(timezone.utc) - agent.last_seen_at
        wait_minutes = int(wait_delta.total_seconds() // 60)
        if effective == TIMED_OUT:
            if wait_minutes >= 60:
                wait_hours = wait_minutes // 60
                rationale = f"Timed out for {wait_hours}h {wait_minutes % 60}m"
            elif wait_minutes > 0:
                rationale = f"Timed out for {wait_minutes}m"
            else:
                rationale = "Timed out"
        else:
            if wait_minutes >= 60:
                wait_hours = wait_minutes // 60
                rationale = f"Awaiting input for {wait_hours}h {wait_minutes % 60}m"
            elif wait_minutes > 0:
                rationale = f"Awaiting input for {wait_minutes}m"
            else:
                rationale = "Awaiting input"

        agent_data = agent_data_map.get(agent.id)
        if agent_data:
            return {
                **agent_data,
                "rationale": rationale,
            }

    # No agents awaiting input - recommend by highest priority score
    active_agents = [a for a in all_agents if is_agent_active(a)]
    if active_agents:
        # Sort by priority_score descending, then last_seen_at descending
        active_agents.sort(
            key=lambda a: (
                a.priority_score if a.priority_score is not None else -1,
                a.last_seen_at,
            ),
            reverse=True,
        )
        agent = active_agents[0]
        agent_data = agent_data_map.get(agent.id)
        if agent_data:
            score = agent.priority_score
            reason = agent.priority_reason
            if score is not None and reason:
                rationale = f"Priority: {score} — {reason}"
            else:
                rationale = "Most recently active"
            return {
                **agent_data,
                "rationale": rationale,
            }

    return None


def sort_agents_by_priority(all_agents_data: list) -> list:
    """
    Sort agents by priority for the By Priority view.

    Order:
    1. Priority score descending (highest first)
    2. State group (AWAITING_INPUT > COMMANDED/PROCESSING > IDLE/COMPLETE)
    3. Last seen descending (most recent first)

    Args:
        all_agents_data: List of agent data dictionaries

    Returns:
        Sorted list of agent data dictionaries
    """

    def priority_key(agent_data):
        # Primary: priority score descending (negate for ascending sort)
        score = agent_data.get("priority", 50)
        if score is None:
            score = 50

        state = agent_data.get("state")
        # Secondary: state group (lower = higher priority)
        if state in (TaskState.AWAITING_INPUT, TIMED_OUT):
            priority_group = 0
        elif state in (TaskState.COMMANDED, TaskState.PROCESSING):
            priority_group = 1
        else:
            priority_group = 2

        # Tertiary: last_seen_at descending
        last_seen = agent_data.get("last_seen_at", datetime.min.replace(tzinfo=timezone.utc))
        return (-score, priority_group, -last_seen.timestamp())

    return sorted(all_agents_data, key=priority_key)


def calculate_status_counts(agents: list[Agent]) -> dict[str, int]:
    """
    Calculate status counts from agent states.

    Args:
        agents: List of agents to count

    Returns:
        Dictionary with timed_out, input_needed, working, and idle counts
    """
    timed_out = 0
    input_needed = 0
    working = 0
    idle = 0

    for agent in agents:
        state = get_effective_state(agent)
        if state == TIMED_OUT:
            timed_out += 1
        elif state == TaskState.AWAITING_INPUT:
            input_needed += 1
        elif state in (TaskState.COMMANDED, TaskState.PROCESSING):
            working += 1
        else:  # IDLE or COMPLETE
            idle += 1

    return {
        "timed_out": timed_out,
        "input_needed": input_needed,
        "working": working,
        "idle": idle,
    }


def get_project_state_flags(agents: list[Agent]) -> dict[str, bool]:
    """
    Determine which agent states are present in a project.

    Args:
        agents: List of agents in the project

    Returns:
        Dictionary with has_timed_out, has_input_needed, has_working, has_idle flags
    """
    flags = {
        "has_timed_out": False,
        "has_input_needed": False,
        "has_working": False,
        "has_idle": False,
    }

    for agent in agents:
        state = get_effective_state(agent)
        if state == TIMED_OUT:
            flags["has_timed_out"] = True
        elif state == TaskState.AWAITING_INPUT:
            flags["has_input_needed"] = True
        elif state in (TaskState.COMMANDED, TaskState.PROCESSING):
            flags["has_working"] = True
        else:
            flags["has_idle"] = True

    return flags


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


def _get_completed_task_summary(task: Task) -> str:
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

    # Default: get most recent turn
    if current_task.turns:
        recent_turn = current_task.turns[-1] if current_task.turns else None
        if recent_turn:
            # Prefer AI-generated summary
            if recent_turn.summary:
                return recent_turn.summary
            # Fall back to raw text
            if recent_turn.text:
                text = recent_turn.text
                if len(text) > 100:
                    return text[:100] + "..."
                return text

    return "No active task"


def get_task_instruction(agent: Agent) -> str | None:
    """
    Get the task instruction for an agent's current or most recent task.

    Args:
        agent: The agent

    Returns:
        Instruction text, or None if no instruction is available
    """
    current_task = agent.get_current_task()
    if current_task and current_task.instruction:
        return current_task.instruction

    # Check most recent completed task
    if agent.tasks and agent.tasks[0].state == TaskState.COMPLETE:
        if agent.tasks[0].instruction:
            return agent.tasks[0].instruction

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


def count_active_agents(agents: list[Agent]) -> int:
    """
    Count active agents in a list.

    Args:
        agents: List of agents

    Returns:
        Count of active agents
    """
    return sum(1 for agent in agents if is_agent_active(agent))


@dashboard_bp.route("/")
@dashboard_bp.route("/dashboard")
def dashboard():
    """
    Main dashboard route showing all projects and agents.

    Query parameters:
        sort: 'project' (default) or 'priority'

    Returns:
        Rendered dashboard template
    """
    # Get sort mode from query parameter (default to 'project')
    sort_mode = request.args.get("sort", "project")
    if sort_mode not in ("project", "priority"):
        sort_mode = "project"

    # Query all projects with eager-loaded relationships
    projects = (
        db.session.query(Project)
        .options(
            selectinload(Project.agents).selectinload(Agent.tasks).selectinload(Task.turns)
        )
        .order_by(Project.name)
        .all()
    )

    # Collect all agents for status counts and recommended next
    all_agents = []
    agent_data_map = {}  # Maps agent.id to agent data dict
    all_agents_data = []  # Flat list of all agent data for priority view

    for project in projects:
        # Exclude ended agents from the dashboard
        active_project_agents = [a for a in project.agents if a.ended_at is None]
        all_agents.extend(active_project_agents)

    # Calculate header status counts
    status_counts = calculate_status_counts(all_agents)

    # Compute staleness for all projects
    staleness_map = {}
    staleness_service = current_app.extensions.get("staleness_service")
    if staleness_service:
        staleness_map = staleness_service.classify_projects(projects)

    # Prepare project data with computed values
    project_data = []
    for project in projects:
        # Exclude ended agents from the dashboard
        live_agents = [a for a in project.agents if a.ended_at is None]
        agents_data = []
        for agent in live_agents:
            effective_state = get_effective_state(agent)
            # state_name: string for templates (handles both TaskState enum and TIMED_OUT string)
            state_name = effective_state if isinstance(effective_state, str) else effective_state.name
            agent_dict = {
                "id": agent.id,
                "session_uuid": str(agent.session_uuid)[:8],
                "is_active": is_agent_active(agent),
                "uptime": format_uptime(agent.started_at),
                "last_seen": format_last_seen(agent.last_seen_at),
                "state": effective_state,
                "state_name": state_name,
                "state_info": get_state_info(effective_state),
                "task_summary": get_task_summary(agent),
                "task_instruction": get_task_instruction(agent),
                "priority": agent.priority_score if agent.priority_score is not None else 50,
                "priority_reason": agent.priority_reason,
                "project_name": project.name,
                "project_id": project.id,
                "last_seen_at": agent.last_seen_at,
            }
            agents_data.append(agent_dict)
            agent_data_map[agent.id] = agent_dict
            all_agents_data.append(agent_dict)

        # Get staleness classification for this project
        staleness_info = staleness_map.get(project.id)
        staleness_dict = None
        if staleness_info:
            staleness_dict = {
                "tier": staleness_info["tier"].value if hasattr(staleness_info["tier"], "value") else staleness_info["tier"],
                "days_since_activity": staleness_info["days_since_activity"],
            }

        project_data.append(
            {
                "id": project.id,
                "name": project.name,
                "state_flags": get_project_state_flags(live_agents),
                "active_count": count_active_agents(live_agents),
                "agents": agents_data,
                "waypoint": None,  # Waypoint will be added in Sprint 9
                "staleness": staleness_dict,
            }
        )

    # Filter out projects with no agents for the Kanban view
    projects_with_agents = [p for p in project_data if p["agents"]]

    # Calculate recommended next agent
    recommended_next = get_recommended_next(all_agents, agent_data_map)

    # Sort agents for priority view
    priority_sorted_agents = sort_agents_by_priority(all_agents_data)

    return render_template(
        "dashboard.html",
        projects=projects_with_agents,
        status_counts=status_counts,
        recommended_next=recommended_next,
        sort_mode=sort_mode,
        priority_sorted_agents=priority_sorted_agents,
    )
