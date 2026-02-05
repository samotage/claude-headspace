"""Dashboard route for agent monitoring."""

from datetime import datetime, timedelta, timezone

from flask import Blueprint, current_app, render_template, request
from sqlalchemy.orm import selectinload

from ..database import db
from ..models import Agent, Project, Task, TaskState
from ..models.objective import Objective
from ..services.card_state import (
    TIMED_OUT,
    _get_current_task_elapsed,
    _get_current_task_turn_count,
    format_last_seen,
    format_uptime,
    get_effective_state,
    get_state_info,
    get_task_completion_summary,
    get_task_instruction,
    get_task_summary,
    is_agent_active,
)

dashboard_bp = Blueprint("dashboard", __name__)


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


def count_active_agents(agents: list[Agent]) -> int:
    """
    Count active agents in a list.

    Args:
        agents: List of agents

    Returns:
        Count of active agents
    """
    return sum(1 for agent in agents if is_agent_active(agent))


def _prepare_kanban_data(
    projects: list, project_data: list, priority_enabled: bool
) -> list:
    """Prepare Kanban board data grouped by project and task state.

    Each project gets columns for each task lifecycle state.
    Idle agents (no active task) go in the IDLE column.
    Agents with active tasks go in the column matching the task state.
    Completed tasks appear in the COMPLETE column.

    Args:
        projects: List of Project model instances
        project_data: List of project data dicts (with agents)
        priority_enabled: Whether priority ordering is enabled

    Returns:
        List of dicts, each with project info and state columns
    """
    columns = ["IDLE", "PROCESSING", "AWAITING_INPUT", "COMPLETE"]
    kanban_projects = []

    for proj_data in project_data:
        if not proj_data["agents"]:
            continue

        # Find matching Project model
        project_model = None
        for p in projects:
            if p.id == proj_data["id"]:
                project_model = p
                break

        state_columns = {col: [] for col in columns}

        if project_model:
            # Get live agents for this project
            live_agents = [a for a in project_model.agents if a.ended_at is None]

            for agent in live_agents:
                # Find the agent data dict
                agent_data = None
                for ad in proj_data["agents"]:
                    if ad["id"] == agent.id:
                        agent_data = ad
                        break
                if not agent_data:
                    continue

                current_task = agent.get_current_task()
                effective_state = get_effective_state(agent)
                state_name = effective_state if isinstance(effective_state, str) else effective_state.name

                if current_task is None or state_name in ("IDLE", "COMPLETE"):
                    # Agent is idle (or just completed a task — completed tasks
                    # are added as condensed accordion cards by the loop below).
                    # Override display state to IDLE so the card renders correctly.
                    idle_data = agent_data
                    if state_name == "COMPLETE":
                        idle_data = {
                            **agent_data,
                            "state": TaskState.IDLE,
                            "state_name": "IDLE",
                            "state_info": get_state_info(TaskState.IDLE),
                            "task_summary": "No active task",
                            "task_instruction": None,
                            "task_completion_summary": None,
                        }
                    state_columns["IDLE"].append({
                        "type": "agent",
                        "agent": idle_data,
                    })
                else:
                    # Agent has active task - goes in the state's column
                    # COMMANDED is a transitory state; display in PROCESSING column
                    col_name = "PROCESSING" if state_name in ("COMMANDED", "TIMED_OUT") else state_name
                    state_columns[col_name].append({
                        "type": "task",
                        "agent": agent_data,
                        "task_instruction": agent_data.get("task_instruction"),
                        "task_summary": agent_data.get("task_summary"),
                        "state": state_name,
                    })

                # Add all completed tasks to COMPLETE column as condensed accordion cards
                if agent.tasks:
                    for task in agent.tasks:
                        if task.state != TaskState.COMPLETE:
                            continue

                        completion_summary = task.completion_summary
                        if not completion_summary and task.turns:
                            last_turn = task.turns[-1]
                            completion_summary = last_turn.summary or (
                                last_turn.text[:100] + "..." if last_turn.text and len(last_turn.text) > 100 else last_turn.text
                            )
                        # Compute elapsed time
                        elapsed = None
                        if task.started_at and task.completed_at:
                            delta = task.completed_at - task.started_at
                            total_seconds = int(delta.total_seconds())
                            hours = total_seconds // 3600
                            minutes = (total_seconds % 3600) // 60
                            if hours > 0:
                                elapsed = f"{hours}h {minutes}m"
                            elif minutes > 0:
                                elapsed = f"{minutes}m"
                            else:
                                elapsed = "<1m"

                        state_columns["COMPLETE"].append({
                            "type": "completed_task",
                            "agent": agent_data,
                            "task_id": task.id,
                            "completion_summary": completion_summary or "Completed",
                            "instruction": task.instruction or "Task",
                            "completed_at": task.completed_at,
                            "turn_count": len(task.turns),
                            "elapsed": elapsed,
                        })

        # Apply priority ordering within columns
        if priority_enabled:
            for col in columns:
                state_columns[col].sort(
                    key=lambda x: -(x["agent"].get("priority", 50) or 50)
                )

        kanban_projects.append({
            "id": proj_data["id"],
            "name": proj_data["name"],
            "slug": proj_data["slug"],
            "columns": state_columns,
            "staleness": proj_data.get("staleness"),
        })

    return kanban_projects


def _get_dashboard_activity_metrics() -> dict | None:
    """Fetch daily activity metrics for the dashboard activity bar.

    Aggregates ALL overall ActivityMetric buckets for the current day
    (midnight UTC to now) to show full-day totals.
    Also includes immediate frustration from HeadspaceMonitor.
    """
    from ..models.activity_metric import ActivityMetric
    from ..models.headspace_snapshot import HeadspaceSnapshot

    try:
        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        # Get ALL overall metrics for today
        today_metrics = (
            db.session.query(ActivityMetric)
            .filter(
                ActivityMetric.is_overall == True,
                ActivityMetric.bucket_start >= today_start,
            )
            .order_by(ActivityMetric.bucket_start.asc())
            .all()
        )

        if not today_metrics:
            return None

        # Aggregate daily totals
        total_turns = sum(m.turn_count or 0 for m in today_metrics)

        # Weighted average turn time across all buckets
        weighted_time_sum = 0.0
        weighted_time_count = 0
        for m in today_metrics:
            if m.avg_turn_time_seconds is not None and m.turn_count and m.turn_count >= 2:
                weight = m.turn_count - 1  # number of deltas
                weighted_time_sum += m.avg_turn_time_seconds * weight
                weighted_time_count += weight
        avg_turn_time = (weighted_time_sum / weighted_time_count) if weighted_time_count > 0 else None

        # Count distinct agents active today from agent-level metrics
        distinct_agents = (
            db.session.query(db.func.count(db.func.distinct(ActivityMetric.agent_id)))
            .filter(
                ActivityMetric.agent_id.isnot(None),
                ActivityMetric.bucket_start >= today_start,
            )
            .scalar()
        ) or 0

        # Turn rate: total turns / hours elapsed today (at least 1 hour)
        hours_elapsed = max((now - today_start).total_seconds() / 3600, 1.0)
        turn_rate = round(total_turns / hours_elapsed, 1)

        # Frustration: aggregate across all buckets
        total_frustration = sum(m.total_frustration or 0 for m in today_metrics)
        total_frust_turns = sum(m.frustration_turn_count or 0 for m in today_metrics)
        frustration_avg = round(total_frustration / total_frust_turns, 1) if total_frust_turns > 0 else None

        # Try to get immediate frustration (last 10 turns) from headspace
        immediate_frustration = None
        try:
            latest_snapshot = (
                db.session.query(HeadspaceSnapshot)
                .order_by(HeadspaceSnapshot.created_at.desc())
                .first()
            )
            if latest_snapshot and latest_snapshot.frustration_rolling_10 is not None:
                immediate_frustration = round(latest_snapshot.frustration_rolling_10, 1)
        except Exception:
            pass

        return {
            "total_turns": total_turns,
            "turn_rate": turn_rate,
            "avg_turn_time": round(avg_turn_time, 1) if avg_turn_time else None,
            "active_agents": distinct_agents,
            "frustration": immediate_frustration if immediate_frustration is not None else frustration_avg,
        }
    except Exception:
        return None


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
    # Get sort mode from query parameter (default to 'kanban')
    sort_mode = request.args.get("sort", "kanban")
    if sort_mode not in ("kanban", "project", "priority"):
        sort_mode = "kanban"

    # Query all projects with eager-loaded relationships
    projects = (
        db.session.query(Project)
        .options(
            selectinload(Project.agents).selectinload(Agent.tasks)
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
            truncated_uuid = str(agent.session_uuid)[:8]
            agent_dict = {
                "id": agent.id,
                "session_uuid": truncated_uuid,
                "hero_chars": truncated_uuid[:2],
                "hero_trail": truncated_uuid[2:],
                "is_active": is_agent_active(agent),
                "uptime": format_uptime(agent.started_at),
                "last_seen": format_last_seen(agent.last_seen_at),
                "state": effective_state,
                "state_name": state_name,
                "state_info": get_state_info(effective_state),
                "task_summary": get_task_summary(agent),
                "task_instruction": get_task_instruction(agent),
                "task_completion_summary": get_task_completion_summary(agent),
                "priority": agent.priority_score if agent.priority_score is not None else 50,
                "priority_reason": agent.priority_reason,
                "turn_count": _get_current_task_turn_count(agent),
                "elapsed": _get_current_task_elapsed(agent),
                "project_name": project.name,
                "project_slug": project.slug,
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
                "slug": project.slug,
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

    # Get current objective
    objective = db.session.query(Objective).first()

    # Sort agents within each project by priority when prioritisation is enabled
    if objective and objective.priority_enabled:
        for project in projects_with_agents:
            project["agents"] = sort_agents_by_priority(project["agents"])

    # Prepare Kanban data (group by task lifecycle state per project)
    kanban_data = []
    if sort_mode == "kanban":
        kanban_data = _prepare_kanban_data(
            projects, project_data, objective and objective.priority_enabled
        )

    # Activity metrics are fetched client-side via JS to use the browser's
    # local timezone for "today" boundaries (matching the activity page).
    # Server-side computation used UTC midnight which gave wrong results
    # for non-UTC timezones.

    return render_template(
        "dashboard.html",
        projects=projects_with_agents,
        status_counts=status_counts,
        recommended_next=recommended_next,
        sort_mode=sort_mode,
        priority_sorted_agents=priority_sorted_agents,
        objective=objective,
        kanban_data=kanban_data,
        activity_metrics=None,
    )
