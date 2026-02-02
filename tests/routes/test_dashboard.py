"""Tests for the dashboard route."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from flask import Flask

from src.claude_headspace.models import TaskState
from src.claude_headspace.models.turn import TurnActor, TurnIntent
from src.claude_headspace.routes.dashboard import (
    calculate_status_counts,
    count_active_agents,
    dashboard_bp,
    get_project_state_flags,
)
from src.claude_headspace.services.card_state import (
    TIMED_OUT,
    _get_completed_task_summary,
    format_uptime,
    get_effective_state,
    get_state_info,
    get_task_completion_summary,
    get_task_instruction,
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

    @patch("src.claude_headspace.services.card_state._get_dashboard_config")
    def test_working_states(self, mock_config):
        """Test agents in working states (COMMANDED and PROCESSING)."""
        mock_config.return_value = {"stale_processing_seconds": 600, "active_timeout_minutes": 5}
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

    @patch("src.claude_headspace.services.card_state._get_dashboard_config")
    def test_mixed_states(self, mock_config):
        """Test with all different states."""
        mock_config.return_value = {"stale_processing_seconds": 600, "active_timeout_minutes": 5}
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

    @patch("src.claude_headspace.services.card_state._get_dashboard_config")
    def test_working_flag(self, mock_config):
        """Test that working agents set has_working."""
        mock_config.return_value = {"stale_processing_seconds": 600, "active_timeout_minutes": 5}
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

    @patch("src.claude_headspace.services.card_state._get_dashboard_config")
    def test_mixed_states(self, mock_config):
        """Test that mixed states set multiple flags."""
        mock_config.return_value = {"stale_processing_seconds": 600, "active_timeout_minutes": 5}
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

    def test_awaiting_input_prefers_agent_question_turn(self):
        """When AWAITING_INPUT, should show agent's question not user's command."""
        from claude_headspace.models.turn import TurnActor, TurnIntent

        agent = MagicMock()
        agent.id = 1

        # User command turn
        user_turn = MagicMock()
        user_turn.actor = TurnActor.USER
        user_turn.intent = TurnIntent.COMMAND
        user_turn.text = "Fix the login bug"
        user_turn.summary = None

        # Agent question turn
        agent_turn = MagicMock()
        agent_turn.actor = TurnActor.AGENT
        agent_turn.intent = TurnIntent.QUESTION
        agent_turn.text = "Which database should we use?"
        agent_turn.summary = None

        mock_task = MagicMock()
        mock_task.state = TaskState.AWAITING_INPUT
        mock_task.turns = [user_turn, agent_turn]
        agent.get_current_task.return_value = mock_task

        result = get_task_summary(agent)
        assert result == "Which database should we use?"

    def test_awaiting_input_prefers_agent_question_summary(self):
        """When AWAITING_INPUT, should prefer AI summary of agent question."""
        from claude_headspace.models.turn import TurnActor, TurnIntent

        agent = MagicMock()
        agent.id = 1

        agent_turn = MagicMock()
        agent_turn.actor = TurnActor.AGENT
        agent_turn.intent = TurnIntent.QUESTION
        agent_turn.text = "Which database should we use for the new feature?"
        agent_turn.summary = "Asking about database choice"

        mock_task = MagicMock()
        mock_task.state = TaskState.AWAITING_INPUT
        mock_task.turns = [agent_turn]
        agent.get_current_task.return_value = mock_task

        result = get_task_summary(agent)
        assert result == "Asking about database choice"

    def test_awaiting_input_falls_back_without_question_turn(self):
        """When AWAITING_INPUT with no AGENT QUESTION turn, should fall back to most recent."""
        from claude_headspace.models.turn import TurnActor, TurnIntent

        agent = MagicMock()
        agent.id = 1

        user_turn = MagicMock()
        user_turn.actor = TurnActor.USER
        user_turn.intent = TurnIntent.COMMAND
        user_turn.text = "Fix the login bug"
        user_turn.summary = None

        mock_task = MagicMock()
        mock_task.state = TaskState.AWAITING_INPUT
        mock_task.turns = [user_turn]
        agent.get_current_task.return_value = mock_task

        result = get_task_summary(agent)
        assert result == "Fix the login bug"

    def test_awaiting_input_truncates_long_question(self):
        """When AWAITING_INPUT, long agent question text should be truncated."""
        from claude_headspace.models.turn import TurnActor, TurnIntent

        agent = MagicMock()
        agent.id = 1

        agent_turn = MagicMock()
        agent_turn.actor = TurnActor.AGENT
        agent_turn.intent = TurnIntent.QUESTION
        agent_turn.text = "Q" * 150
        agent_turn.summary = None

        mock_task = MagicMock()
        mock_task.state = TaskState.AWAITING_INPUT
        mock_task.turns = [agent_turn]
        agent.get_current_task.return_value = mock_task

        result = get_task_summary(agent)
        assert len(result) == 103  # 100 chars + "..."
        assert result.endswith("...")


class TestGetCompletedTaskSummary:
    """Tests for _get_completed_task_summary helper."""

    def test_returns_task_summary_when_set(self):
        """Completed task with task.completion_summary returns that summary."""
        mock_task = MagicMock()
        mock_task.completion_summary = "Refactored authentication module"
        mock_task.turns = []
        result = _get_completed_task_summary(mock_task)
        assert result == "Refactored authentication module"

    def test_falls_back_to_last_turn_summary(self):
        """Completed task without task.completion_summary uses last turn's summary."""
        mock_turn = MagicMock()
        mock_turn.summary = "Fixed login bug"
        mock_turn.text = "Raw turn text here"

        mock_task = MagicMock()
        mock_task.completion_summary = None
        mock_task.turns = [mock_turn]
        result = _get_completed_task_summary(mock_task)
        assert result == "Fixed login bug"

    def test_falls_back_to_last_turn_text(self):
        """Completed task without summaries uses last turn's raw text."""
        mock_turn = MagicMock()
        mock_turn.summary = None
        mock_turn.text = "Implemented the feature"

        mock_task = MagicMock()
        mock_task.completion_summary = None
        mock_task.turns = [mock_turn]
        result = _get_completed_task_summary(mock_task)
        assert result == "Implemented the feature"

    def test_truncates_long_turn_text(self):
        """Long last turn text is truncated to 100 chars."""
        mock_turn = MagicMock()
        mock_turn.summary = None
        mock_turn.text = "A" * 150

        mock_task = MagicMock()
        mock_task.completion_summary = None
        mock_task.turns = [mock_turn]
        result = _get_completed_task_summary(mock_task)
        assert len(result) == 103  # 100 + "..."
        assert result.endswith("...")

    def test_no_turns_returns_summarising(self):
        """Completed task with no turns returns 'Summarising...'."""
        mock_task = MagicMock()
        mock_task.completion_summary = None
        mock_task.turns = []
        result = _get_completed_task_summary(mock_task)
        assert result == "Summarising..."

    def test_prefers_task_summary_over_turn_summary(self):
        """task.completion_summary takes priority over turn summary."""
        mock_turn = MagicMock()
        mock_turn.summary = "Turn-level summary"
        mock_turn.text = "Raw text"

        mock_task = MagicMock()
        mock_task.completion_summary = "Task-level summary"
        mock_task.turns = [mock_turn]
        result = _get_completed_task_summary(mock_task)
        assert result == "Task-level summary"


class TestGetTaskSummaryCompletedFallback:
    """Tests for get_task_summary() completed task fallback path."""

    def test_completed_task_with_summary(self):
        """When no active task but most recent is COMPLETE with summary, shows it."""
        agent = MagicMock()
        agent.get_current_task.return_value = None

        completed_task = MagicMock()
        completed_task.state = TaskState.COMPLETE
        completed_task.completion_summary = "Deployed new API endpoint"
        completed_task.turns = []
        agent.tasks = [completed_task]

        result = get_task_summary(agent)
        assert result == "Deployed new API endpoint"

    def test_completed_task_falls_back_to_turn_text(self):
        """Completed task without summary falls back to turn text."""
        agent = MagicMock()
        agent.get_current_task.return_value = None

        mock_turn = MagicMock()
        mock_turn.summary = None
        mock_turn.text = "Done with the refactor"

        completed_task = MagicMock()
        completed_task.state = TaskState.COMPLETE
        completed_task.completion_summary = None
        completed_task.turns = [mock_turn]
        agent.tasks = [completed_task]

        result = get_task_summary(agent)
        assert result == "Done with the refactor"

    def test_completed_task_prefers_turn_summary_over_text(self):
        """Completed task prefers turn summary over raw text."""
        agent = MagicMock()
        agent.get_current_task.return_value = None

        mock_turn = MagicMock()
        mock_turn.summary = "Completed authentication refactor"
        mock_turn.text = "Raw text that should not be used"

        completed_task = MagicMock()
        completed_task.state = TaskState.COMPLETE
        completed_task.completion_summary = None
        completed_task.turns = [mock_turn]
        agent.tasks = [completed_task]

        result = get_task_summary(agent)
        assert result == "Completed authentication refactor"

    def test_completed_task_no_summary_no_turns(self):
        """Completed task with no summary and no turns shows 'Summarising...'."""
        agent = MagicMock()
        agent.get_current_task.return_value = None

        completed_task = MagicMock()
        completed_task.state = TaskState.COMPLETE
        completed_task.completion_summary = None
        completed_task.turns = []
        agent.tasks = [completed_task]

        result = get_task_summary(agent)
        assert result == "Summarising..."

    def test_no_tasks_shows_no_active_task(self):
        """Agent with no tasks at all shows 'No active task'."""
        agent = MagicMock()
        agent.get_current_task.return_value = None
        agent.tasks = []

        result = get_task_summary(agent)
        assert result == "No active task"

    def test_most_recent_task_not_complete_shows_no_active_task(self):
        """When most recent task is not COMPLETE, shows 'No active task'."""
        agent = MagicMock()
        agent.get_current_task.return_value = None

        idle_task = MagicMock()
        idle_task.state = TaskState.IDLE
        idle_task.completion_summary = "Some old task"
        agent.tasks = [idle_task]

        result = get_task_summary(agent)
        assert result == "No active task"


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
        """Test that status badges are rendered in the stats bar."""
        response = client.get("/")
        html = response.data.decode("utf-8")
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
    """Tests for dashboard with mocked database data.

    Uses a standalone Flask app with only the dashboard blueprint,
    avoiding any dependency on the test database.
    """

    @pytest.fixture
    def standalone_app(self):
        """Create a standalone Flask app with dashboard blueprint (no DB needed).

        Registers the minimal set of blueprints needed for template
        rendering (navigation links use url_for to other blueprints).
        """
        from pathlib import Path
        from src.claude_headspace.routes.config import config_bp
        from src.claude_headspace.routes.help import help_bp
        from src.claude_headspace.routes.logging import logging_bp
        from src.claude_headspace.routes.objective import objective_bp

        project_root = Path(__file__).parent.parent.parent
        app = Flask(
            __name__,
            template_folder=str(project_root / "templates"),
            static_folder=str(project_root / "static"),
        )
        app.register_blueprint(dashboard_bp)
        app.register_blueprint(config_bp)
        app.register_blueprint(help_bp)
        app.register_blueprint(logging_bp)
        app.register_blueprint(objective_bp)
        app.config["TESTING"] = True
        app.config["APP_CONFIG"] = {
            "dashboard": {
                "stale_processing_seconds": 600,
                "active_timeout_minutes": 5,
            },
        }
        # Provide extensions so service lookups don't fail
        app.extensions["staleness_service"] = None
        return app

    @pytest.fixture
    def standalone_client(self, standalone_app):
        """Test client for standalone app."""
        return standalone_app.test_client()

    @pytest.fixture
    def mock_db_session(self):
        """Create a mock database session."""
        with patch("src.claude_headspace.routes.dashboard.db") as mock_db:
            yield mock_db

    def test_projects_displayed(self, standalone_client, mock_db_session):
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

        response = standalone_client.get("/")
        assert response.status_code == 200

    def test_state_dots_displayed(self, standalone_client, mock_db_session):
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

        response = standalone_client.get("/")
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

    @patch("src.claude_headspace.services.card_state._get_dashboard_config")
    def test_stale_processing_returns_timed_out(self, mock_config):
        """Test that PROCESSING agent past threshold returns TIMED_OUT."""
        mock_config.return_value = {"stale_processing_seconds": 600}

        # Agent has been PROCESSING for 700 seconds (> 600s config value)
        agent = create_mock_agent(state=TaskState.PROCESSING)
        agent.last_seen_at = datetime.now(timezone.utc) - timedelta(seconds=700)

        result = get_effective_state(agent)
        assert result == TIMED_OUT

    @patch("src.claude_headspace.services.card_state._get_dashboard_config")
    def test_recent_processing_stays_processing(self, mock_config):
        """Test that PROCESSING agent within threshold stays PROCESSING."""
        mock_config.return_value = {"stale_processing_seconds": 600}

        # Agent has been PROCESSING for 30 seconds (< 600s config value)
        agent = create_mock_agent(state=TaskState.PROCESSING)
        agent.last_seen_at = datetime.now(timezone.utc) - timedelta(seconds=30)

        result = get_effective_state(agent)
        assert result == TaskState.PROCESSING

    @patch("src.claude_headspace.services.card_state._get_dashboard_config")
    def test_timed_out_counted_separately(self, mock_config):
        """Test that TIMED_OUT agents are counted in timed_out, not input_needed."""
        mock_config.return_value = {"stale_processing_seconds": 600}

        # One TIMED_OUT, one AWAITING_INPUT, one IDLE
        stale_agent = create_mock_agent(state=TaskState.PROCESSING)
        stale_agent.last_seen_at = datetime.now(timezone.utc) - timedelta(seconds=700)

        waiting_agent = create_mock_agent(state=TaskState.AWAITING_INPUT)
        idle_agent = create_mock_agent(state=TaskState.IDLE)

        result = calculate_status_counts([stale_agent, waiting_agent, idle_agent])
        assert result["timed_out"] == 1
        assert result["input_needed"] == 1
        assert result["idle"] == 1

    @patch("src.claude_headspace.services.card_state._get_dashboard_config")
    def test_timed_out_project_state_flag(self, mock_config):
        """Test that TIMED_OUT agents set has_timed_out flag."""
        mock_config.return_value = {"stale_processing_seconds": 600}

        stale_agent = create_mock_agent(state=TaskState.PROCESSING)
        stale_agent.last_seen_at = datetime.now(timezone.utc) - timedelta(seconds=700)

        result = get_project_state_flags([stale_agent])
        assert result["has_timed_out"] is True
        assert result["has_input_needed"] is False


class TestGetTaskInstruction:
    """Tests for get_task_instruction() helper."""

    def test_returns_instruction_from_current_task(self):
        """Test that instruction is returned from current active task."""
        agent = MagicMock()
        mock_task = MagicMock()
        mock_task.instruction = "Fix the login page"
        agent.get_current_task.return_value = mock_task

        result = get_task_instruction(agent)

        assert result == "Fix the login page"

    def test_returns_none_when_no_current_task(self):
        """Test returns None when agent has no current task."""
        agent = MagicMock()
        agent.get_current_task.return_value = None
        agent.tasks = []

        result = get_task_instruction(agent)

        assert result is None

    def test_returns_none_when_current_task_has_no_instruction(self):
        """Test returns None when current task has no instruction yet."""
        agent = MagicMock()
        mock_task = MagicMock()
        mock_task.instruction = None
        agent.get_current_task.return_value = mock_task
        agent.tasks = []

        result = get_task_instruction(agent)

        assert result is None

    def test_falls_back_to_completed_task_instruction(self):
        """Test falls back to most recent completed task instruction."""
        agent = MagicMock()
        agent.get_current_task.return_value = None

        completed_task = MagicMock()
        completed_task.state = TaskState.COMPLETE
        completed_task.instruction = "Refactor auth module"
        agent.tasks = [completed_task]

        result = get_task_instruction(agent)

        assert result == "Refactor auth module"

    def test_falls_back_to_most_recent_task_instruction_any_state(self):
        """Test falls back to most recent task instruction regardless of state."""
        agent = MagicMock()
        agent.get_current_task.return_value = None

        processing_task = MagicMock()
        processing_task.state = TaskState.PROCESSING
        processing_task.instruction = "Some instruction"
        agent.tasks = [processing_task]

        result = get_task_instruction(agent)

        assert result == "Some instruction"

    def test_falls_back_to_raw_command_text(self):
        """Test falls back to first USER COMMAND turn's raw text when no instruction."""
        agent = MagicMock()
        agent.get_current_task.return_value = None

        turn = MagicMock()
        turn.actor = TurnActor.USER
        turn.intent = TurnIntent.COMMAND
        turn.text = "Fix the login page bug"

        task = MagicMock()
        task.instruction = None
        task.state = TaskState.COMPLETE
        task.turns = [turn]
        agent.tasks = [task]

        result = get_task_instruction(agent)

        assert result == "Fix the login page bug"

    def test_raw_command_text_truncated_at_80_chars(self):
        """Test raw command text is truncated to 80 chars."""
        agent = MagicMock()
        agent.get_current_task.return_value = None

        turn = MagicMock()
        turn.actor = TurnActor.USER
        turn.intent = TurnIntent.COMMAND
        turn.text = "x" * 100

        task = MagicMock()
        task.instruction = None
        task.state = TaskState.COMPLETE
        task.turns = [turn]
        agent.tasks = [task]

        result = get_task_instruction(agent)

        assert result == "x" * 77 + "..."
        assert len(result) == 80

    def test_task_without_instruction_or_turns_returns_none(self):
        """Test task with no instruction and no turns returns None."""
        agent = MagicMock()
        agent.get_current_task.return_value = None

        task = MagicMock()
        task.instruction = None
        task.state = TaskState.COMPLETE
        task.turns = []
        agent.tasks = [task]

        result = get_task_instruction(agent)

        assert result is None


class TestGetTaskCompletionSummary:
    """Tests for get_task_completion_summary() helper."""

    def test_returns_completion_summary(self):
        """Test returns completion_summary from completed task."""
        agent = MagicMock()
        task = MagicMock()
        task.state = TaskState.COMPLETE
        task.completion_summary = "Auth module refactored successfully"
        agent.tasks = [task]

        result = get_task_completion_summary(agent)

        assert result == "Auth module refactored successfully"

    def test_falls_back_to_last_turn_summary(self):
        """Test falls back to last turn's summary when no completion_summary."""
        agent = MagicMock()

        turn = MagicMock()
        turn.summary = "Finished refactoring the auth module"

        task = MagicMock()
        task.state = TaskState.COMPLETE
        task.completion_summary = None
        task.turns = [turn]
        agent.tasks = [task]

        result = get_task_completion_summary(agent)

        assert result == "Finished refactoring the auth module"

    def test_returns_none_when_no_real_summary(self):
        """Test returns None when no summaries available."""
        agent = MagicMock()

        turn = MagicMock()
        turn.summary = None

        task = MagicMock()
        task.state = TaskState.COMPLETE
        task.completion_summary = None
        task.turns = [turn]
        agent.tasks = [task]

        result = get_task_completion_summary(agent)

        assert result is None

    def test_returns_none_when_no_completed_task(self):
        """Test returns None when only active tasks exist."""
        agent = MagicMock()

        task = MagicMock()
        task.state = TaskState.PROCESSING
        agent.tasks = [task]

        result = get_task_completion_summary(agent)

        assert result is None

    def test_returns_none_when_no_tasks(self):
        """Test returns None when agent has no tasks."""
        agent = MagicMock()
        agent.tasks = []

        result = get_task_completion_summary(agent)

        assert result is None

    def test_skips_non_complete_finds_complete(self):
        """Test skips non-complete tasks to find the first complete one."""
        agent = MagicMock()

        active_task = MagicMock()
        active_task.state = TaskState.PROCESSING

        completed_task = MagicMock()
        completed_task.state = TaskState.COMPLETE
        completed_task.completion_summary = "Done"

        agent.tasks = [active_task, completed_task]

        result = get_task_completion_summary(agent)

        assert result == "Done"
