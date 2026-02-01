"""Tests for the dashboard route."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from flask import Flask

from src.claude_headspace.models import TaskState
from src.claude_headspace.routes.dashboard import (
    TIMED_OUT,
    calculate_status_counts,
    count_active_agents,
    dashboard_bp,
    format_uptime,
    get_effective_state,
    get_project_state_flags,
    get_state_info,
    get_task_summary,
    is_agent_active,
)


# --- Helper Functions for Mock Data ---


def create_mock_agent(
    state: TaskState = TaskState.IDLE,
    last_seen_minutes_ago: int = 0,
    started_hours_ago: int = 1,
    task_text: str | None = None,
):
    """Create a mock agent with specified properties."""
    agent = MagicMock()
    agent.id = 1
    agent.session_uuid = uuid4()
    agent.state = state
    agent.last_seen_at = datetime.now(timezone.utc) - timedelta(minutes=last_seen_minutes_ago)
    agent.started_at = datetime.now(timezone.utc) - timedelta(hours=started_hours_ago)
    agent.ended_at = None

    # Mock get_current_task
    if task_text:
        mock_turn = MagicMock()
        mock_turn.text = task_text
        mock_turn.summary = None
        mock_task = MagicMock()
        mock_task.turns = [mock_turn]
        agent.get_current_task.return_value = mock_task
    else:
        agent.get_current_task.return_value = None

    return agent


# --- Unit Tests for Helper Functions ---


class TestCalculateStatusCounts:
    """Tests for calculate_status_counts function."""

    def test_empty_agents_list(self):
        """Test with no agents."""
        result = calculate_status_counts([])
        assert result == {"timed_out": 0, "input_needed": 0, "working": 0, "idle": 0}

    def test_all_idle(self):
        """Test with all idle agents."""
        agents = [
            create_mock_agent(state=TaskState.IDLE),
            create_mock_agent(state=TaskState.IDLE),
        ]
        result = calculate_status_counts(agents)
        assert result == {"timed_out": 0, "input_needed": 0, "working": 0, "idle": 2}

    def test_awaiting_input(self):
        """Test agents awaiting input."""
        agents = [
            create_mock_agent(state=TaskState.AWAITING_INPUT),
            create_mock_agent(state=TaskState.IDLE),
        ]
        result = calculate_status_counts(agents)
        assert result == {"timed_out": 0, "input_needed": 1, "working": 0, "idle": 1}

    def test_working_states(self):
        """Test agents in working states (COMMANDED and PROCESSING)."""
        agents = [
            create_mock_agent(state=TaskState.COMMANDED),
            create_mock_agent(state=TaskState.PROCESSING),
            create_mock_agent(state=TaskState.IDLE),
        ]
        result = calculate_status_counts(agents)
        assert result == {"timed_out": 0, "input_needed": 0, "working": 2, "idle": 1}

    def test_complete_counts_as_idle(self):
        """Test that COMPLETE state counts as idle."""
        agents = [
            create_mock_agent(state=TaskState.COMPLETE),
        ]
        result = calculate_status_counts(agents)
        assert result == {"timed_out": 0, "input_needed": 0, "working": 0, "idle": 1}

    def test_mixed_states(self):
        """Test with all different states."""
        agents = [
            create_mock_agent(state=TaskState.IDLE),
            create_mock_agent(state=TaskState.COMMANDED),
            create_mock_agent(state=TaskState.PROCESSING),
            create_mock_agent(state=TaskState.AWAITING_INPUT),
            create_mock_agent(state=TaskState.COMPLETE),
        ]
        result = calculate_status_counts(agents)
        assert result == {"timed_out": 0, "input_needed": 1, "working": 2, "idle": 2}


class TestGetProjectStateFlags:
    """Tests for get_project_state_flags function."""

    def test_empty_agents_all_false(self):
        """Test that no agents returns all flags false."""
        result = get_project_state_flags([])
        assert result == {
            "has_timed_out": False,
            "has_input_needed": False,
            "has_working": False,
            "has_idle": False,
        }

    def test_awaiting_input_flag(self):
        """Test that agent awaiting input sets has_input_needed."""
        agents = [
            create_mock_agent(state=TaskState.AWAITING_INPUT),
        ]
        result = get_project_state_flags(agents)
        assert result["has_timed_out"] is False
        assert result["has_input_needed"] is True
        assert result["has_working"] is False
        assert result["has_idle"] is False

    def test_working_flag(self):
        """Test that working agents set has_working."""
        agents = [
            create_mock_agent(state=TaskState.PROCESSING),
            create_mock_agent(state=TaskState.COMMANDED),
        ]
        result = get_project_state_flags(agents)
        assert result["has_timed_out"] is False
        assert result["has_input_needed"] is False
        assert result["has_working"] is True
        assert result["has_idle"] is False

    def test_idle_flag(self):
        """Test that idle agents set has_idle."""
        agents = [
            create_mock_agent(state=TaskState.IDLE),
        ]
        result = get_project_state_flags(agents)
        assert result["has_timed_out"] is False
        assert result["has_input_needed"] is False
        assert result["has_working"] is False
        assert result["has_idle"] is True

    def test_complete_counts_as_idle(self):
        """Test that COMPLETE state sets has_idle."""
        agents = [
            create_mock_agent(state=TaskState.COMPLETE),
        ]
        result = get_project_state_flags(agents)
        assert result["has_idle"] is True

    def test_mixed_states(self):
        """Test that mixed states set multiple flags."""
        agents = [
            create_mock_agent(state=TaskState.AWAITING_INPUT),
            create_mock_agent(state=TaskState.PROCESSING),
            create_mock_agent(state=TaskState.IDLE),
        ]
        result = get_project_state_flags(agents)
        assert result["has_timed_out"] is False
        assert result["has_input_needed"] is True
        assert result["has_working"] is True
        assert result["has_idle"] is True


class TestIsAgentActive:
    """Tests for is_agent_active function."""

    def test_recently_seen_is_active(self):
        """Test agent seen recently is active."""
        agent = create_mock_agent(last_seen_minutes_ago=1)
        assert is_agent_active(agent) is True

    def test_just_under_timeout_is_active(self):
        """Test agent just under timeout boundary is active."""
        agent = create_mock_agent(last_seen_minutes_ago=4)
        assert is_agent_active(agent) is True

    def test_past_timeout_is_inactive(self):
        """Test agent past timeout is inactive."""
        agent = create_mock_agent(last_seen_minutes_ago=6)
        assert is_agent_active(agent) is False

    def test_long_ago_is_inactive(self):
        """Test agent seen long ago is inactive."""
        agent = create_mock_agent(last_seen_minutes_ago=60)
        assert is_agent_active(agent) is False


class TestFormatUptime:
    """Tests for format_uptime function."""

    def test_hours_and_minutes(self):
        """Test formatting with hours and minutes."""
        started_at = datetime.now(timezone.utc) - timedelta(hours=32, minutes=38)
        result = format_uptime(started_at)
        assert result == "up 32h 38m"

    def test_hours_only(self):
        """Test formatting with full hours."""
        started_at = datetime.now(timezone.utc) - timedelta(hours=5)
        result = format_uptime(started_at)
        assert result == "up 5h 0m"

    def test_minutes_only(self):
        """Test formatting with only minutes."""
        started_at = datetime.now(timezone.utc) - timedelta(minutes=45)
        result = format_uptime(started_at)
        assert result == "up 45m"

    def test_less_than_minute(self):
        """Test formatting with less than a minute."""
        started_at = datetime.now(timezone.utc) - timedelta(seconds=30)
        result = format_uptime(started_at)
        assert result == "up <1m"


class TestGetTaskSummary:
    """Tests for get_task_summary function."""

    def test_no_current_task(self):
        """Test when agent has no current task."""
        agent = create_mock_agent(task_text=None)
        result = get_task_summary(agent)
        assert result == "No active task"

    def test_short_task_text(self):
        """Test with short task text."""
        agent = create_mock_agent(task_text="Fix the bug")
        result = get_task_summary(agent)
        assert result == "Fix the bug"

    def test_long_task_text_truncated(self):
        """Test that long text is truncated to 100 chars."""
        long_text = "A" * 150
        agent = create_mock_agent(task_text=long_text)
        result = get_task_summary(agent)
        assert len(result) == 103  # 100 chars + "..."
        assert result.endswith("...")

    def test_exactly_100_chars(self):
        """Test with exactly 100 characters."""
        text = "A" * 100
        agent = create_mock_agent(task_text=text)
        result = get_task_summary(agent)
        assert result == text
        assert len(result) == 100


class TestGetStateInfo:
    """Tests for get_state_info function."""

    def test_idle_state(self):
        """Test IDLE state info."""
        result = get_state_info(TaskState.IDLE)
        assert result["color"] == "green"
        assert result["bg_class"] == "bg-green"
        assert "Idle" in result["label"]

    def test_commanded_state(self):
        """Test COMMANDED state info."""
        result = get_state_info(TaskState.COMMANDED)
        assert result["color"] == "yellow"
        assert result["bg_class"] == "bg-amber"
        assert "Command" in result["label"]

    def test_processing_state(self):
        """Test PROCESSING state info."""
        result = get_state_info(TaskState.PROCESSING)
        assert result["color"] == "blue"
        assert result["bg_class"] == "bg-blue"
        assert "Processing" in result["label"]

    def test_awaiting_input_state(self):
        """Test AWAITING_INPUT state info."""
        result = get_state_info(TaskState.AWAITING_INPUT)
        assert result["color"] == "orange"
        assert result["bg_class"] == "bg-amber"
        assert "Input" in result["label"]

    def test_complete_state(self):
        """Test COMPLETE state info."""
        result = get_state_info(TaskState.COMPLETE)
        assert result["color"] == "green"
        assert result["bg_class"] == "bg-green"
        assert "complete" in result["label"].lower()


class TestCountActiveAgents:
    """Tests for count_active_agents function."""

    def test_empty_list(self):
        """Test with no agents."""
        result = count_active_agents([])
        assert result == 0

    def test_all_active(self):
        """Test with all active agents."""
        agents = [
            create_mock_agent(last_seen_minutes_ago=1),
            create_mock_agent(last_seen_minutes_ago=2),
        ]
        result = count_active_agents(agents)
        assert result == 2

    def test_all_inactive(self):
        """Test with all inactive agents."""
        agents = [
            create_mock_agent(last_seen_minutes_ago=10),
            create_mock_agent(last_seen_minutes_ago=20),
        ]
        result = count_active_agents(agents)
        assert result == 0

    def test_mixed_activity(self):
        """Test with mixed active and inactive agents."""
        agents = [
            create_mock_agent(last_seen_minutes_ago=1),  # active
            create_mock_agent(last_seen_minutes_ago=10),  # inactive
            create_mock_agent(last_seen_minutes_ago=3),  # active
        ]
        result = count_active_agents(agents)
        assert result == 2


# --- Integration Tests for Dashboard Route ---


@pytest.fixture
def dashboard_app():
    """Create a Flask app with dashboard blueprint for testing."""
    app = Flask(__name__, template_folder="../../templates")
    app.register_blueprint(dashboard_bp)
    app.config["TESTING"] = True
    return app


@pytest.fixture
def dashboard_client(dashboard_app):
    """Create a test client for dashboard tests."""
    return dashboard_app.test_client()


class TestDashboardRoute:
    """Integration tests for the dashboard route."""

    def test_dashboard_returns_200(self, client):
        """Test that dashboard route returns 200 OK."""
        response = client.get("/")
        assert response.status_code == 200

    def test_dashboard_route_alias(self, client):
        """Test that /dashboard also works."""
        response = client.get("/dashboard")
        assert response.status_code == 200

    def test_dashboard_renders_template(self, client):
        """Test that dashboard renders the correct template."""
        response = client.get("/")
        # Check for key elements in the template
        html = response.data.decode("utf-8")
        assert "CLAUDE" in html
        assert "headspace" in html

    def test_dashboard_shows_status_badges(self, client):
        """Test that status badges are rendered."""
        response = client.get("/")
        html = response.data.decode("utf-8")
        assert "TIMED OUT" in html
        assert "INPUT NEEDED" in html
        assert "WORKING" in html
        assert "IDLE" in html

    def test_dashboard_shows_navigation(self, client):
        """Test that navigation tabs are rendered."""
        response = client.get("/")
        html = response.data.decode("utf-8")
        assert "dashboard" in html.lower()
        assert "objective" in html.lower()
        assert "logging" in html.lower()

    def test_dashboard_shows_connection_indicator(self, client):
        """Test that connection indicator is shown."""
        response = client.get("/")
        html = response.data.decode("utf-8")
        # Sprint 8b replaced POLLING with SSE connection indicator
        assert "connection-indicator" in html

    def test_empty_projects_message(self, client):
        """Test message shown when no projects exist."""
        response = client.get("/")
        html = response.data.decode("utf-8")
        # Empty state message
        assert "No projects found" in html or "projects" in html.lower()


class TestDashboardWithData:
    """Tests for dashboard with mocked database data."""

    @pytest.fixture
    def mock_db_session(self):
        """Create a mock database session."""
        with patch("src.claude_headspace.routes.dashboard.db") as mock_db:
            yield mock_db

    def test_projects_displayed(self, client, mock_db_session):
        """Test that projects are displayed when data exists."""
        # Create mock project with agents
        mock_agent = create_mock_agent(
            state=TaskState.PROCESSING,
            last_seen_minutes_ago=1,
        )

        mock_project = MagicMock()
        mock_project.id = 1
        mock_project.name = "Test Project"
        mock_project.agents = [mock_agent]

        # Configure the mock query chain
        mock_query = MagicMock()
        mock_query.options.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = [mock_project]
        mock_db_session.session.query.return_value = mock_query

        response = client.get("/")
        assert response.status_code == 200

    def test_state_dots_displayed(self, client, mock_db_session):
        """Test that state indicator dots are shown."""
        mock_agent = create_mock_agent(state=TaskState.AWAITING_INPUT)

        mock_project = MagicMock()
        mock_project.id = 1
        mock_project.name = "Needs Input Project"
        mock_project.agents = [mock_agent]

        mock_query = MagicMock()
        mock_query.options.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = [mock_project]
        mock_db_session.session.query.return_value = mock_query

        response = client.get("/")
        html = response.data.decode("utf-8")
        # State dots should be present
        assert "state-dot" in html
        assert response.status_code == 200


class TestDashboardAccessibility:
    """Tests for dashboard accessibility features."""

    def test_header_has_banner_role(self, client):
        """Test that header has banner role."""
        response = client.get("/")
        html = response.data.decode("utf-8")
        assert 'role="banner"' in html

    def test_main_has_main_role(self, client):
        """Test that main content has main role."""
        response = client.get("/")
        html = response.data.decode("utf-8")
        assert 'role="main"' in html

    def test_navigation_has_nav_role(self, client):
        """Test that navigation has navigation role."""
        response = client.get("/")
        html = response.data.decode("utf-8")
        assert 'role="navigation"' in html

    def test_aria_labels_present(self, client):
        """Test that ARIA labels are used."""
        response = client.get("/")
        html = response.data.decode("utf-8")
        assert "aria-label" in html


class TestTimedOutState:
    """Tests for the TIMED_OUT display-only state."""

    def test_timed_out_state_info(self):
        """Test that get_state_info returns correct info for TIMED_OUT."""
        result = get_state_info(TIMED_OUT)
        assert result["color"] == "red"
        assert result["bg_class"] == "bg-red"
        assert "Timed out" in result["label"]

    @patch("src.claude_headspace.routes.dashboard.get_agent_display_state")
    def test_stale_processing_returns_timed_out(self, mock_display_state):
        """Test that PROCESSING agent past threshold returns TIMED_OUT."""
        mock_display_state.return_value = None

        # Agent has been PROCESSING for 700 seconds (> 600s default)
        agent = create_mock_agent(state=TaskState.PROCESSING)
        agent.last_seen_at = datetime.now(timezone.utc) - timedelta(seconds=700)

        result = get_effective_state(agent)
        assert result == TIMED_OUT

    @patch("src.claude_headspace.routes.dashboard.get_agent_display_state")
    def test_recent_processing_stays_processing(self, mock_display_state):
        """Test that PROCESSING agent within threshold stays PROCESSING."""
        mock_display_state.return_value = None

        # Agent has been PROCESSING for 30 seconds (< 600s default)
        agent = create_mock_agent(state=TaskState.PROCESSING)
        agent.last_seen_at = datetime.now(timezone.utc) - timedelta(seconds=30)

        result = get_effective_state(agent)
        assert result == TaskState.PROCESSING

    @patch("src.claude_headspace.routes.dashboard.get_agent_display_state")
    def test_timed_out_counted_separately(self, mock_display_state):
        """Test that TIMED_OUT agents are counted in timed_out, not input_needed."""
        mock_display_state.return_value = None

        # One TIMED_OUT, one AWAITING_INPUT, one IDLE
        stale_agent = create_mock_agent(state=TaskState.PROCESSING)
        stale_agent.last_seen_at = datetime.now(timezone.utc) - timedelta(seconds=700)

        waiting_agent = create_mock_agent(state=TaskState.AWAITING_INPUT)
        idle_agent = create_mock_agent(state=TaskState.IDLE)

        result = calculate_status_counts([stale_agent, waiting_agent, idle_agent])
        assert result["timed_out"] == 1
        assert result["input_needed"] == 1
        assert result["idle"] == 1

    @patch("src.claude_headspace.routes.dashboard.get_agent_display_state")
    def test_timed_out_project_state_flag(self, mock_display_state):
        """Test that TIMED_OUT agents set has_timed_out flag."""
        mock_display_state.return_value = None

        stale_agent = create_mock_agent(state=TaskState.PROCESSING)
        stale_agent.last_seen_at = datetime.now(timezone.utc) - timedelta(seconds=700)

        result = get_project_state_flags([stale_agent])
        assert result["has_timed_out"] is True
        assert result["has_input_needed"] is False
