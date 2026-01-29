"""Dashboard route for agent monitoring."""

from datetime import datetime, timedelta, timezone

from flask import Blueprint, render_template, request
from sqlalchemy.orm import selectinload

from ..database import db
from ..models import Agent, Project, Task, TaskState

dashboard_bp = Blueprint("dashboard", __name__)

# Constants
ACTIVE_TIMEOUT_MINUTES = 5  # Agent is ACTIVE if last_seen_at within this time


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

    # Filter to agents awaiting input
    awaiting_input = [a for a in all_agents if a.state == TaskState.AWAITING_INPUT]

    if awaiting_input:
        # Sort by last_seen_at ascending (oldest waiting first)
        awaiting_input.sort(key=lambda a: a.last_seen_at)
        agent = awaiting_input[0]

        # Calculate wait time
        wait_delta = datetime.now(timezone.utc) - agent.last_seen_at
        wait_minutes = int(wait_delta.total_seconds() // 60)
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

    # No agents awaiting input - get most recently active
    active_agents = [a for a in all_agents if is_agent_active(a)]
    if active_agents:
        # Sort by last_seen_at descending (most recent first)
        active_agents.sort(key=lambda a: a.last_seen_at, reverse=True)
        agent = active_agents[0]
        agent_data = agent_data_map.get(agent.id)
        if agent_data:
            return {
                **agent_data,
                "rationale": "Most recently active",
            }

    return None


def sort_agents_by_priority(all_agents_data: list) -> list:
    """
    Sort agents by priority for the By Priority view.

    Order:
    1. AWAITING_INPUT (by last_seen_at descending)
    2. COMMANDED/PROCESSING (by last_seen_at descending)
    3. IDLE/COMPLETE (by last_seen_at descending)

    Args:
        all_agents_data: List of agent data dictionaries

    Returns:
        Sorted list of agent data dictionaries
    """

    def priority_key(agent_data):
        state = agent_data.get("state")
        # Lower number = higher priority
        if state == TaskState.AWAITING_INPUT:
            priority_group = 0
        elif state in (TaskState.COMMANDED, TaskState.PROCESSING):
            priority_group = 1
        else:
            priority_group = 2

        # Within group, sort by last_seen_at descending (most recent first)
        # We use negative timestamp for descending order
        last_seen = agent_data.get("last_seen_at", datetime.min.replace(tzinfo=timezone.utc))
        return (priority_group, -last_seen.timestamp())

    return sorted(all_agents_data, key=priority_key)


def calculate_status_counts(agents: list[Agent]) -> dict[str, int]:
    """
    Calculate status counts from agent states.

    Args:
        agents: List of agents to count

    Returns:
        Dictionary with input_needed, working, and idle counts
    """
    input_needed = 0
    working = 0
    idle = 0

    for agent in agents:
        state = agent.state
        if state == TaskState.AWAITING_INPUT:
            input_needed += 1
        elif state in (TaskState.COMMANDED, TaskState.PROCESSING):
            working += 1
        else:  # IDLE or COMPLETE
            idle += 1

    return {
        "input_needed": input_needed,
        "working": working,
        "idle": idle,
    }


def get_traffic_light_color(agents: list[Agent]) -> str:
    """
    Determine traffic light color based on agent states.

    Args:
        agents: List of agents in the project

    Returns:
        Color string: 'red', 'yellow', or 'green'
    """
    if not agents:
        return "green"

    for agent in agents:
        if agent.state == TaskState.AWAITING_INPUT:
            return "red"

    for agent in agents:
        if agent.state in (TaskState.COMMANDED, TaskState.PROCESSING):
            return "yellow"

    return "green"


def is_agent_active(agent: Agent) -> bool:
    """
    Check if an agent is active based on last_seen_at.

    Args:
        agent: The agent to check

    Returns:
        True if active (seen within timeout), False otherwise
    """
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=ACTIVE_TIMEOUT_MINUTES)
    return agent.last_seen_at >= cutoff


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


def get_task_summary(agent: Agent) -> str:
    """
    Get task summary for an agent.

    Args:
        agent: The agent

    Returns:
        First 100 chars of most recent turn text, or "No active task"
    """
    current_task = agent.get_current_task()
    if current_task is None:
        return "No active task"

    # Get most recent turn
    if current_task.turns:
        # Turns are ordered by timestamp, get the last one
        recent_turn = current_task.turns[-1] if current_task.turns else None
        if recent_turn and recent_turn.text:
            text = recent_turn.text
            if len(text) > 100:
                return text[:100] + "..."
            return text

    return "No active task"


def get_state_info(state: TaskState) -> dict:
    """
    Get display info for a task state.

    Args:
        state: The TaskState enum value

    Returns:
        Dictionary with color and label
    """
    state_map = {
        TaskState.IDLE: {
            "color": "gray",
            "bg_class": "bg-muted",
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
        all_agents.extend(project.agents)

    # Calculate header status counts
    status_counts = calculate_status_counts(all_agents)

    # Prepare project data with computed values
    project_data = []
    for project in projects:
        agents_data = []
        for agent in project.agents:
            agent_dict = {
                "id": agent.id,
                "session_uuid": str(agent.session_uuid)[:8],
                "is_active": is_agent_active(agent),
                "uptime": format_uptime(agent.started_at),
                "state": agent.state,
                "state_info": get_state_info(agent.state),
                "task_summary": get_task_summary(agent),
                "priority": 50,  # Default priority for Epic 1
                "project_name": project.name,
                "project_id": project.id,
                "last_seen_at": agent.last_seen_at,
            }
            agents_data.append(agent_dict)
            agent_data_map[agent.id] = agent_dict
            all_agents_data.append(agent_dict)

        project_data.append(
            {
                "id": project.id,
                "name": project.name,
                "traffic_light": get_traffic_light_color(project.agents),
                "active_count": count_active_agents(project.agents),
                "agents": agents_data,
                "waypoint": None,  # Waypoint will be added in Sprint 9
            }
        )

    # Calculate recommended next agent
    recommended_next = get_recommended_next(all_agents, agent_data_map)

    # Sort agents for priority view
    priority_sorted_agents = sort_agents_by_priority(all_agents_data)

    return render_template(
        "dashboard.html",
        projects=project_data,
        status_counts=status_counts,
        recommended_next=recommended_next,
        sort_mode=sort_mode,
        priority_sorted_agents=priority_sorted_agents,
    )
