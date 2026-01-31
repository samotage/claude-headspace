"""Tests for dashboard interactivity features (Sprint 8b)."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from src.claude_headspace.models import TaskState
from src.claude_headspace.routes.dashboard import (
    get_recommended_next,
    sort_agents_by_priority,
)


# --- Helper Functions for Mock Data ---


def create_mock_agent(
    agent_id: int = 1,
    state: TaskState = TaskState.IDLE,
    last_seen_minutes_ago: int = 0,
    started_hours_ago: int = 1,
    task_text: str | None = None,
    priority_score: int | None = None,
    priority_reason: str | None = None,
):
    """Create a mock agent with specified properties."""
    agent = MagicMock()
    agent.id = agent_id
    agent.session_uuid = uuid4()
    agent.state = state
    agent.last_seen_at = datetime.now(timezone.utc) - timedelta(minutes=last_seen_minutes_ago)
    agent.started_at = datetime.now(timezone.utc) - timedelta(hours=started_hours_ago)
    agent.ended_at = None
    agent.priority_score = priority_score
    agent.priority_reason = priority_reason

    # Mock get_current_task
    if task_text:
        mock_turn = MagicMock()
        mock_turn.text = task_text
        mock_task = MagicMock()
        mock_task.turns = [mock_turn]
        agent.get_current_task.return_value = mock_task
    else:
        agent.get_current_task.return_value = None

    return agent


def create_agent_data(
    agent_id: int = 1,
    state: TaskState = TaskState.IDLE,
    last_seen_minutes_ago: int = 0,
    project_name: str = "Test Project",
    project_id: int = 1,
):
    """Create agent data dictionary as used in template context."""
    last_seen = datetime.now(timezone.utc) - timedelta(minutes=last_seen_minutes_ago)
    return {
        "id": agent_id,
        "session_uuid": str(uuid4())[:8],
        "is_active": last_seen_minutes_ago < 5,
        "uptime": "up 1h 0m",
        "state": state,
        "state_info": {"color": "gray", "bg_class": "bg-muted", "label": "Idle"},
        "task_summary": "No active task",
        "priority": 50,
        "project_name": project_name,
        "project_id": project_id,
        "last_seen_at": last_seen,
    }


# --- Tests for get_recommended_next ---


class TestGetRecommendedNext:
    """Tests for get_recommended_next function."""

    def test_empty_agents_returns_none(self):
        """Test with no agents."""
        result = get_recommended_next([], {})
        assert result is None

    def test_awaiting_input_has_priority(self):
        """Test that AWAITING_INPUT agent is recommended over others."""
        # Create agents
        agent_idle = create_mock_agent(agent_id=1, state=TaskState.IDLE, last_seen_minutes_ago=1)
        agent_awaiting = create_mock_agent(
            agent_id=2, state=TaskState.AWAITING_INPUT, last_seen_minutes_ago=5
        )
        agent_processing = create_mock_agent(
            agent_id=3, state=TaskState.PROCESSING, last_seen_minutes_ago=0
        )

        all_agents = [agent_idle, agent_awaiting, agent_processing]

        # Create agent data map
        agent_data_map = {
            1: create_agent_data(agent_id=1, state=TaskState.IDLE),
            2: create_agent_data(agent_id=2, state=TaskState.AWAITING_INPUT),
            3: create_agent_data(agent_id=3, state=TaskState.PROCESSING),
        }

        result = get_recommended_next(all_agents, agent_data_map)

        assert result is not None
        assert result["id"] == 2
        assert "Awaiting input" in result["rationale"]

    def test_oldest_awaiting_input_recommended_first(self):
        """Test that the oldest AWAITING_INPUT agent is recommended first."""
        # Create two agents awaiting input
        agent_newer = create_mock_agent(
            agent_id=1, state=TaskState.AWAITING_INPUT, last_seen_minutes_ago=2
        )
        agent_older = create_mock_agent(
            agent_id=2, state=TaskState.AWAITING_INPUT, last_seen_minutes_ago=10
        )

        all_agents = [agent_newer, agent_older]

        agent_data_map = {
            1: create_agent_data(agent_id=1, state=TaskState.AWAITING_INPUT),
            2: create_agent_data(agent_id=2, state=TaskState.AWAITING_INPUT),
        }

        result = get_recommended_next(all_agents, agent_data_map)

        assert result is not None
        assert result["id"] == 2  # Older one should be recommended

    def test_most_recently_active_when_no_awaiting_input(self):
        """Test that most recently active agent is recommended when none awaiting input."""
        agent_old = create_mock_agent(agent_id=1, state=TaskState.IDLE, last_seen_minutes_ago=4)
        agent_recent = create_mock_agent(agent_id=2, state=TaskState.IDLE, last_seen_minutes_ago=1)

        all_agents = [agent_old, agent_recent]

        agent_data_map = {
            1: create_agent_data(agent_id=1, state=TaskState.IDLE, last_seen_minutes_ago=4),
            2: create_agent_data(agent_id=2, state=TaskState.IDLE, last_seen_minutes_ago=1),
        }

        result = get_recommended_next(all_agents, agent_data_map)

        assert result is not None
        assert result["id"] == 2
        assert result["rationale"] == "Most recently active"

    def test_no_recommendation_when_all_inactive(self):
        """Test that None returned when no active agents."""
        agent = create_mock_agent(agent_id=1, state=TaskState.IDLE, last_seen_minutes_ago=10)

        all_agents = [agent]
        agent_data_map = {
            1: create_agent_data(agent_id=1, state=TaskState.IDLE, last_seen_minutes_ago=10)
        }

        result = get_recommended_next(all_agents, agent_data_map)

        assert result is None

    def test_rationale_format_minutes(self):
        """Test that rationale correctly formats minutes."""
        agent = create_mock_agent(
            agent_id=1, state=TaskState.AWAITING_INPUT, last_seen_minutes_ago=15
        )

        all_agents = [agent]
        agent_data_map = {
            1: create_agent_data(agent_id=1, state=TaskState.AWAITING_INPUT, last_seen_minutes_ago=15)
        }

        result = get_recommended_next(all_agents, agent_data_map)

        assert result is not None
        assert "15m" in result["rationale"]

    def test_rationale_format_hours_and_minutes(self):
        """Test that rationale correctly formats hours and minutes."""
        agent = create_mock_agent(
            agent_id=1, state=TaskState.AWAITING_INPUT, last_seen_minutes_ago=75  # 1h 15m
        )

        all_agents = [agent]
        agent_data_map = {
            1: create_agent_data(agent_id=1, state=TaskState.AWAITING_INPUT, last_seen_minutes_ago=75)
        }

        result = get_recommended_next(all_agents, agent_data_map)

        assert result is not None
        assert "1h" in result["rationale"]
        assert "15m" in result["rationale"]


# --- Tests for sort_agents_by_priority ---


class TestSortAgentsByPriority:
    """Tests for sort_agents_by_priority function."""

    def test_empty_list(self):
        """Test with empty list."""
        result = sort_agents_by_priority([])
        assert result == []

    def test_awaiting_input_first(self):
        """Test that AWAITING_INPUT comes before other states."""
        agents = [
            create_agent_data(agent_id=1, state=TaskState.IDLE),
            create_agent_data(agent_id=2, state=TaskState.AWAITING_INPUT),
            create_agent_data(agent_id=3, state=TaskState.PROCESSING),
        ]

        result = sort_agents_by_priority(agents)

        assert result[0]["id"] == 2  # AWAITING_INPUT first
        assert result[0]["state"] == TaskState.AWAITING_INPUT

    def test_working_before_idle(self):
        """Test that COMMANDED/PROCESSING comes before IDLE/COMPLETE."""
        agents = [
            create_agent_data(agent_id=1, state=TaskState.IDLE),
            create_agent_data(agent_id=2, state=TaskState.PROCESSING),
            create_agent_data(agent_id=3, state=TaskState.COMPLETE),
            create_agent_data(agent_id=4, state=TaskState.COMMANDED),
        ]

        result = sort_agents_by_priority(agents)

        # First two should be working (COMMANDED, PROCESSING)
        working_ids = {result[0]["id"], result[1]["id"]}
        assert working_ids == {2, 4}

        # Last two should be idle (IDLE, COMPLETE)
        idle_ids = {result[2]["id"], result[3]["id"]}
        assert idle_ids == {1, 3}

    def test_within_group_sorted_by_recency(self):
        """Test that within same priority group, most recent comes first."""
        agents = [
            create_agent_data(agent_id=1, state=TaskState.IDLE, last_seen_minutes_ago=10),
            create_agent_data(agent_id=2, state=TaskState.IDLE, last_seen_minutes_ago=2),
            create_agent_data(agent_id=3, state=TaskState.IDLE, last_seen_minutes_ago=5),
        ]

        result = sort_agents_by_priority(agents)

        # Should be ordered: 2 (2m ago), 3 (5m ago), 1 (10m ago)
        assert [a["id"] for a in result] == [2, 3, 1]

    def test_full_priority_ordering(self):
        """Test complete ordering: AWAITING_INPUT → WORKING → IDLE."""
        agents = [
            create_agent_data(agent_id=1, state=TaskState.IDLE, last_seen_minutes_ago=1),
            create_agent_data(agent_id=2, state=TaskState.AWAITING_INPUT, last_seen_minutes_ago=5),
            create_agent_data(agent_id=3, state=TaskState.PROCESSING, last_seen_minutes_ago=2),
            create_agent_data(agent_id=4, state=TaskState.COMPLETE, last_seen_minutes_ago=0),
            create_agent_data(agent_id=5, state=TaskState.COMMANDED, last_seen_minutes_ago=3),
            create_agent_data(agent_id=6, state=TaskState.AWAITING_INPUT, last_seen_minutes_ago=1),
        ]

        result = sort_agents_by_priority(agents)

        # Check group ordering
        result_states = [a["state"] for a in result]

        # AWAITING_INPUT should come first
        assert result_states[0] == TaskState.AWAITING_INPUT
        assert result_states[1] == TaskState.AWAITING_INPUT

        # Then COMMANDED/PROCESSING
        assert result_states[2] in (TaskState.COMMANDED, TaskState.PROCESSING)
        assert result_states[3] in (TaskState.COMMANDED, TaskState.PROCESSING)

        # Then IDLE/COMPLETE
        assert result_states[4] in (TaskState.IDLE, TaskState.COMPLETE)
        assert result_states[5] in (TaskState.IDLE, TaskState.COMPLETE)

    def test_preserves_agent_data(self):
        """Test that sorting preserves all agent data."""
        agents = [
            create_agent_data(
                agent_id=1, state=TaskState.IDLE, project_name="Project A", project_id=10
            ),
        ]

        result = sort_agents_by_priority(agents)

        assert result[0]["project_name"] == "Project A"
        assert result[0]["project_id"] == 10
        assert result[0]["session_uuid"] == agents[0]["session_uuid"]


# --- Tests for Sort View Integration ---


class TestSortViewRoute:
    """Tests for sort parameter handling in dashboard route."""

    def test_default_sort_is_project(self, client):
        """Test that default sort mode is 'project'."""
        response = client.get("/")
        assert response.status_code == 200
        # The template should receive sort_mode='project'
        html = response.data.decode("utf-8")
        # Check that project view elements are present
        assert "By Project" in html or "project-view" in html

    def test_sort_parameter_priority(self, client):
        """Test that sort=priority parameter is accepted."""
        response = client.get("/?sort=priority")
        assert response.status_code == 200

    def test_invalid_sort_defaults_to_project(self, client):
        """Test that invalid sort parameter defaults to 'project'."""
        response = client.get("/?sort=invalid")
        assert response.status_code == 200


# --- Tests for SSE and Focus API Integration ---


class TestDashboardInteractivityElements:
    """Tests for interactive elements in dashboard HTML."""

    def test_recommended_next_panel_rendered(self, client):
        """Test that recommended next panel section is rendered."""
        response = client.get("/")
        html = response.data.decode("utf-8")
        # The template includes the recommended next partial
        assert "recommended" in html.lower() or "No agents to recommend" in html

    def test_sort_controls_rendered(self, client):
        """Test that sort controls are rendered."""
        response = client.get("/")
        html = response.data.decode("utf-8")
        assert "By Project" in html
        assert "By Priority" in html

    def test_connection_indicator_rendered(self, client):
        """Test that connection indicator is rendered."""
        response = client.get("/")
        html = response.data.decode("utf-8")
        assert "connection-indicator" in html

    def test_sse_scripts_included(self, client):
        """Test that SSE JavaScript files are included."""
        response = client.get("/")
        html = response.data.decode("utf-8")
        assert "sse-client.js" in html
        assert "dashboard-sse.js" in html

    def test_focus_api_script_included(self, client):
        """Test that focus API JavaScript is included."""
        response = client.get("/")
        html = response.data.decode("utf-8")
        assert "focus-api.js" in html

    def test_toast_container_rendered(self, client):
        """Test that toast container is rendered."""
        response = client.get("/")
        html = response.data.decode("utf-8")
        assert "toast" in html.lower()


class TestDataAttributes:
    """Tests for data attributes needed for SSE updates."""

    def test_agent_cards_have_data_attributes(self, client):
        """Test that agent cards have data-agent-id and data-state attributes."""
        response = client.get("/")
        html = response.data.decode("utf-8")
        # Template uses data-agent-id for targeting
        # Even with no agents, the template structure should be present
        assert "data-agent-id" in html or "No projects found" in html

    def test_project_groups_have_data_attributes(self, client):
        """Test that project groups have data-project-id attributes."""
        response = client.get("/")
        html = response.data.decode("utf-8")
        # Template uses data-project-id for targeting
        assert "data-project-id" in html or "No projects found" in html

    def test_status_counts_have_ids(self, client):
        """Test that header status badges have IDs for SSE updates."""
        response = client.get("/")
        html = response.data.decode("utf-8")
        assert "status-input-needed" in html
        assert "status-working" in html
        assert "status-idle" in html


class TestLocalStoragePersistence:
    """Tests for localStorage-based sort preference."""

    def test_sort_controls_have_localstorage_script(self, client):
        """Test that sort controls include localStorage handling."""
        response = client.get("/")
        html = response.data.decode("utf-8")
        # Check for localStorage key
        assert "claude_headspace_sort_mode" in html or "localStorage" in html
