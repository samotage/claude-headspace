"""Tests for the voice_formatter service (task 3.3)."""

import pytest

from src.claude_headspace.services.voice_formatter import VoiceFormatter


@pytest.fixture
def config():
    """Config with voice bridge settings."""
    return {
        "voice_bridge": {
            "default_verbosity": "concise",
        },
    }


@pytest.fixture
def formatter(config):
    """Create a VoiceFormatter instance."""
    return VoiceFormatter(config=config)


class TestFormatSessions:
    """Test session listing formatting (task 3.3)."""

    def test_no_agents(self, formatter):
        result = formatter.format_sessions([])
        assert result["status_line"] == "No agents are currently running."
        assert result["results"] == []
        assert result["next_action"] == "none"

    def test_single_agent_working(self, formatter):
        agents = [
            {
                "name": "agent-1",
                "project": "my-project",
                "state": "processing",
                "awaiting_input": False,
                "summary": "Running tests",
                "last_activity_ago": "2m ago",
            }
        ]
        result = formatter.format_sessions(agents)
        assert "1 agent running" in result["status_line"]
        assert "None need input" in result["status_line"]
        assert len(result["results"]) == 1
        assert "my-project: processing" in result["results"][0]
        assert result["next_action"] == "none"

    def test_agents_awaiting_input(self, formatter):
        agents = [
            {"name": "a1", "project": "proj-a", "state": "awaiting_input", "awaiting_input": True, "summary": "Q1", "last_activity_ago": "1m ago"},
            {"name": "a2", "project": "proj-b", "state": "processing", "awaiting_input": False, "summary": "Working", "last_activity_ago": "3m ago"},
        ]
        result = formatter.format_sessions(agents)
        assert "2 agents running" in result["status_line"]
        assert "1 needs your input" in result["status_line"]
        assert "Respond to proj-a" in result["next_action"]

    def test_multiple_awaiting(self, formatter):
        agents = [
            {"name": "a1", "project": "proj-a", "state": "awaiting_input", "awaiting_input": True, "summary": None, "last_activity_ago": "1m ago"},
            {"name": "a2", "project": "proj-b", "state": "awaiting_input", "awaiting_input": True, "summary": None, "last_activity_ago": "2m ago"},
        ]
        result = formatter.format_sessions(agents)
        assert "2 need your input" in result["status_line"]
        assert "proj-a" in result["next_action"]
        assert "proj-b" in result["next_action"]

    def test_concise_hides_timestamp(self, formatter):
        agents = [
            {"name": "a1", "project": "proj-a", "state": "processing", "awaiting_input": False, "summary": "Working", "last_activity_ago": "5m ago"},
        ]
        result = formatter.format_sessions(agents, verbosity="concise")
        assert "5m ago" not in result["results"][0]

    def test_normal_shows_timestamp(self, formatter):
        agents = [
            {"name": "a1", "project": "proj-a", "state": "processing", "awaiting_input": False, "summary": "Working", "last_activity_ago": "5m ago"},
        ]
        result = formatter.format_sessions(agents, verbosity="normal")
        assert "5m ago" in result["results"][0]

    def test_summary_included_in_results(self, formatter):
        agents = [
            {"name": "a1", "project": "proj-a", "state": "processing", "awaiting_input": False, "summary": "Deploying to staging", "last_activity_ago": "1m ago"},
        ]
        result = formatter.format_sessions(agents)
        assert "Deploying to staging" in result["results"][0]


class TestFormatCommandResult:
    """Test command result formatting (task 3.3)."""

    def test_success(self, formatter):
        result = formatter.format_command_result("agent-1", True)
        assert "Command sent to agent-1" in result["status_line"]
        assert result["next_action"] == "none"

    def test_failure(self, formatter):
        result = formatter.format_command_result("agent-1", False, "Pane not found")
        assert "Could not send" in result["status_line"]
        assert "Pane not found" in result["results"]

    def test_failure_unknown_error(self, formatter):
        result = formatter.format_command_result("agent-1", False)
        assert "Unknown error" in result["results"]


class TestFormatQuestion:
    """Test question detail formatting (task 3.3)."""

    def test_structured_question_with_options(self, formatter):
        agent_data = {
            "project": "my-project",
            "question_text": "Which database should we use?",
            "question_options": [
                {"label": "PostgreSQL", "description": "Relational DB"},
                {"label": "MongoDB", "description": "Document DB"},
            ],
            "question_source_type": "ask_user_question",
        }
        result = formatter.format_question(agent_data)
        assert "my-project is asking" in result["status_line"]
        assert any("Which database" in r for r in result["results"])
        assert any("PostgreSQL" in r for r in result["results"])
        assert any("MongoDB" in r for r in result["results"])
        assert "option number" in result["next_action"]

    def test_free_text_question(self, formatter):
        agent_data = {
            "project": "my-project",
            "question_text": "What should the API endpoint be named?",
            "question_options": None,
            "question_source_type": "free_text",
        }
        result = formatter.format_question(agent_data)
        assert "Speak your answer" in result["next_action"]
        assert "option" not in result["next_action"]

    def test_question_with_no_text(self, formatter):
        agent_data = {
            "project": "my-project",
            "question_options": None,
            "question_source_type": "unknown",
        }
        # question_text not present — falls back to default
        result = formatter.format_question(agent_data)
        assert "No question text available" in result["results"][0]


class TestFormatOutput:
    """Test output formatting with verbosity levels (task 3.3)."""

    def test_no_tasks(self, formatter):
        result = formatter.format_output("agent-1", [])
        assert "No recent activity" in result["status_line"]
        assert result["results"] == []

    def test_concise_verbosity(self, formatter):
        tasks = [
            {"instruction": "Fix login bug", "completion_summary": "Fixed auth validation", "state": "complete", "full_command": None, "full_output": None},
        ]
        result = formatter.format_output("agent-1", tasks, verbosity="concise")
        assert len(result["results"]) == 1
        assert result["results"][0] == "Fixed auth validation"

    def test_concise_falls_back_to_instruction(self, formatter):
        tasks = [
            {"instruction": "Fix login bug", "completion_summary": None, "state": "processing", "full_command": None, "full_output": None},
        ]
        result = formatter.format_output("agent-1", tasks, verbosity="concise")
        assert result["results"][0] == "Fix login bug"

    def test_normal_verbosity(self, formatter):
        tasks = [
            {"instruction": "Fix login bug", "completion_summary": "Fixed it", "state": "complete", "full_command": None, "full_output": None},
        ]
        result = formatter.format_output("agent-1", tasks, verbosity="normal")
        assert "Fix login bug: Fixed it" in result["results"][0]

    def test_detailed_verbosity_includes_command_and_output(self, formatter):
        tasks = [
            {
                "instruction": "Run tests",
                "completion_summary": "All passed",
                "state": "complete",
                "full_command": "pytest -v tests/",
                "full_output": "5 passed, 0 failed",
            },
        ]
        result = formatter.format_output("agent-1", tasks, verbosity="detailed")
        assert any("Task: Run tests" in r for r in result["results"])
        assert any("Command: pytest" in r for r in result["results"])
        assert any("Output: 5 passed" in r for r in result["results"])

    def test_status_line_includes_count(self, formatter):
        tasks = [
            {"instruction": "t1", "completion_summary": "done", "state": "complete", "full_command": None, "full_output": None},
            {"instruction": "t2", "completion_summary": "done", "state": "complete", "full_command": None, "full_output": None},
        ]
        result = formatter.format_output("agent-1", tasks)
        assert "2 tasks" in result["status_line"]

    def test_default_verbosity_from_config(self):
        config = {"voice_bridge": {"default_verbosity": "normal"}}
        formatter = VoiceFormatter(config=config)
        tasks = [
            {"instruction": "Fix bug", "completion_summary": "Fixed", "state": "complete", "full_command": None, "full_output": None},
        ]
        result = formatter.format_output("agent-1", tasks)
        # normal includes both instruction and summary
        assert "Fix bug: Fixed" in result["results"][0]


class TestFormatError:
    """Test error formatting (task 3.3)."""

    def test_format_error(self, formatter):
        result = formatter.format_error("Something went wrong.", "Try again later.")
        assert result["status_line"] == "Something went wrong."
        assert result["results"] == []
        assert result["next_action"] == "Try again later."
