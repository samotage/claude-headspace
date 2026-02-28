"""Tests for handoff_executor service module."""

import os
import tempfile
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from claude_headspace.services.handoff_executor import (
    HandoffExecutor,
    HandoffResult,
    reset_handoff_state,
)


@pytest.fixture(autouse=True)
def _reset_handoff():
    """Reset handoff state before each test."""
    reset_handoff_state()
    yield
    reset_handoff_state()


def _make_agent(
    agent_id=1,
    ended=False,
    persona_slug="developer-con-1",
    tmux_pane_id="%5",
    project_name="test-project",
    previous_agent_id=None,
):
    """Create a mock agent."""
    agent = MagicMock()
    agent.id = agent_id
    agent.ended_at = datetime.now(timezone.utc) if ended else None
    agent.persona_id = 10 if persona_slug else None
    agent.tmux_pane_id = tmux_pane_id
    agent.project_id = 1

    persona = MagicMock()
    persona.slug = persona_slug
    persona.name = "Developer Con 1"
    agent.persona = persona if persona_slug else None

    project = MagicMock()
    project.name = project_name
    agent.project = project

    agent.previous_agent_id = previous_agent_id
    agent.name = f"Agent {agent_id}"

    return agent


class TestValidatePreconditions:
    """Tests for precondition validation (task 3.1)."""

    def test_agent_not_found(self, app):
        with app.app_context():
            executor = HandoffExecutor(app=app)
            with patch(
                "claude_headspace.services.handoff_executor.db"
            ) as mock_db:
                mock_db.session.get.return_value = None
                result = executor.validate_preconditions(999)

        assert not result.success
        assert result.error_code == "not_found"

    def test_agent_not_active(self, app):
        with app.app_context():
            executor = HandoffExecutor(app=app)
            agent = _make_agent(ended=True)
            with patch(
                "claude_headspace.services.handoff_executor.db"
            ) as mock_db:
                mock_db.session.get.return_value = agent
                result = executor.validate_preconditions(1)

        assert not result.success
        assert result.error_code == "not_active"

    def test_agent_no_persona(self, app):
        with app.app_context():
            executor = HandoffExecutor(app=app)
            agent = _make_agent(persona_slug=None)
            agent.persona_id = None
            with patch(
                "claude_headspace.services.handoff_executor.db"
            ) as mock_db:
                mock_db.session.get.return_value = agent
                result = executor.validate_preconditions(1)

        assert not result.success
        assert result.error_code == "no_persona"

    def test_agent_no_tmux_pane(self, app):
        with app.app_context():
            executor = HandoffExecutor(app=app)
            agent = _make_agent(tmux_pane_id=None)
            with patch(
                "claude_headspace.services.handoff_executor.db"
            ) as mock_db:
                mock_db.session.get.return_value = agent
                result = executor.validate_preconditions(1)

        assert not result.success
        assert result.error_code == "no_tmux_pane"

    def test_already_has_handoff(self, app):
        with app.app_context():
            executor = HandoffExecutor(app=app)
            agent = _make_agent()
            with patch(
                "claude_headspace.services.handoff_executor.db"
            ) as mock_db, patch(
                "claude_headspace.services.handoff_executor.Handoff"
            ) as mock_handoff:
                mock_db.session.get.return_value = agent
                mock_handoff.query.filter_by.return_value.first.return_value = (
                    MagicMock()
                )
                result = executor.validate_preconditions(1)

        assert not result.success
        assert result.error_code == "already_in_progress"

    def test_preconditions_met(self, app):
        with app.app_context():
            executor = HandoffExecutor(app=app)
            agent = _make_agent()
            with patch(
                "claude_headspace.services.handoff_executor.db"
            ) as mock_db, patch(
                "claude_headspace.services.handoff_executor.Handoff"
            ) as mock_handoff:
                mock_db.session.get.return_value = agent
                mock_handoff.query.filter_by.return_value.first.return_value = (
                    None
                )
                result = executor.validate_preconditions(1)

        assert result.success
        assert result.message == "Preconditions met"


class TestGenerateHandoffFilePath:
    """Tests for handoff file path generation (task 3.2)."""

    def test_path_format(self, app):
        executor = HandoffExecutor(app=app)
        agent = _make_agent(agent_id=42)

        path = executor.generate_handoff_file_path(agent)

        # Path must be absolute so agents write to the correct location
        # regardless of their working directory
        assert os.path.isabs(path), f"Expected absolute path, got: {path}"
        assert "data/personas/developer-con-1/handoffs/" in path
        assert path.endswith("-00000042.md")
        # Check timestamp format (YYYYMMDDTHHmmss)
        filename = path.split("/")[-1]
        timestamp_part = filename.split("-")[0]
        assert len(timestamp_part) == 15  # YYYYMMDDTHHmmss
        assert "T" in timestamp_part

    def test_path_zero_padded_agent_id(self, app):
        executor = HandoffExecutor(app=app)
        agent = _make_agent(agent_id=7)

        path = executor.generate_handoff_file_path(agent)

        assert "-00000007.md" in path

    def test_path_large_agent_id(self, app):
        executor = HandoffExecutor(app=app)
        agent = _make_agent(agent_id=12345678)

        path = executor.generate_handoff_file_path(agent)

        assert "-12345678.md" in path


class TestComposeHandoffInstruction:
    """Tests for handoff instruction composition (task 3.3)."""

    def test_instruction_contains_file_path(self, app):
        executor = HandoffExecutor(app=app)
        file_path = "data/personas/dev/handoffs/20260101T120000-00000001.md"

        instruction = executor.compose_handoff_instruction(file_path)

        assert file_path in instruction

    def test_instruction_contains_required_sections(self, app):
        executor = HandoffExecutor(app=app)
        instruction = executor.compose_handoff_instruction("test.md")

        assert "Current work" in instruction
        assert "Progress" in instruction
        assert "Decisions" in instruction
        assert "Blockers" in instruction
        assert "Files modified" in instruction
        assert "Next steps" in instruction

    def test_instruction_does_not_mention_exit(self, app):
        """Handoff instruction should NOT tell the agent to /exit.

        The outgoing agent stays alive; the successor is created alongside it.
        """
        executor = HandoffExecutor(app=app)
        instruction = executor.compose_handoff_instruction("test.md")

        assert "/exit" not in instruction


class TestVerifyHandoffFile:
    """Tests for handoff file verification (task 3.4)."""

    def test_file_not_found(self, app):
        executor = HandoffExecutor(app=app)
        result = executor.verify_handoff_file("/nonexistent/path.md")

        assert not result.success
        assert result.error_code == "file_not_found"

    def test_file_empty(self, app, tmp_path):
        executor = HandoffExecutor(app=app)
        empty_file = tmp_path / "empty.md"
        empty_file.touch()

        result = executor.verify_handoff_file(str(empty_file))

        assert not result.success
        assert result.error_code == "file_empty"

    def test_file_valid(self, app, tmp_path):
        executor = HandoffExecutor(app=app)
        valid_file = tmp_path / "handoff.md"
        valid_file.write_text("# Handoff Document\nSome content here.")

        result = executor.verify_handoff_file(str(valid_file))

        assert result.success


class TestComposeInjectionPrompt:
    """Tests for injection prompt composition (task 3.6)."""

    def test_prompt_references_predecessor(self, app):
        executor = HandoffExecutor(app=app)
        agent = _make_agent(agent_id=42)
        file_path = "data/personas/dev/handoffs/test.md"

        prompt = executor.compose_injection_prompt(agent, file_path)

        assert "Agent #42" in prompt
        assert "Developer Con 1" in prompt
        assert "test-project" in prompt
        assert file_path in prompt

    def test_prompt_instructs_to_read_file(self, app):
        executor = HandoffExecutor(app=app)
        agent = _make_agent()

        prompt = executor.compose_injection_prompt(agent, "handoff.md")

        assert "Read" in prompt or "read" in prompt.lower()
        assert "handoff.md" in prompt


class TestTriggerHandoff:
    """Tests for trigger_handoff (tasks 3.5, integration)."""

    def test_trigger_success(self, app):
        with app.app_context():
            executor = HandoffExecutor(app=app)
            agent = _make_agent()

            with patch.object(
                executor, "validate_preconditions"
            ) as mock_validate, patch(
                "claude_headspace.services.handoff_executor.db"
            ) as mock_db, patch(
                "claude_headspace.services.tmux_bridge"
            ) as mock_tmux:
                mock_validate.return_value = HandoffResult(
                    success=True, message="OK"
                )
                mock_db.session.get.return_value = agent
                mock_tmux.send_text.return_value = MagicMock(success=True)

                result = executor.trigger_handoff(1, reason="context_limit")

        assert result.success
        assert result.message == "Handoff initiated"
        assert executor.is_handoff_in_progress(1)

    def test_trigger_validation_failure(self, app):
        with app.app_context():
            executor = HandoffExecutor(app=app)

            with patch.object(executor, "validate_preconditions") as mock_v:
                mock_v.return_value = HandoffResult(
                    success=False,
                    message="Agent not found",
                    error_code="not_found",
                )

                result = executor.trigger_handoff(999, reason="test")

        assert not result.success
        assert result.error_code == "not_found"

    def test_trigger_tmux_send_failure(self, app):
        with app.app_context():
            executor = HandoffExecutor(app=app)
            agent = _make_agent()

            with patch.object(
                executor, "validate_preconditions"
            ) as mock_validate, patch(
                "claude_headspace.services.handoff_executor.db"
            ) as mock_db, patch(
                "claude_headspace.services.tmux_bridge"
            ) as mock_tmux, patch.object(
                executor, "_broadcast_error"
            ):
                mock_validate.return_value = HandoffResult(
                    success=True, message="OK"
                )
                mock_db.session.get.return_value = agent
                mock_tmux.send_text.return_value = MagicMock(
                    success=False, error_message="Pane not found"
                )

                result = executor.trigger_handoff(1, reason="test")

        assert not result.success
        assert result.error_code == "send_failed"
        assert not executor.is_handoff_in_progress(1)


class TestHandoffInProgressFlag:
    """Tests for in-memory handoff tracking."""

    def test_not_in_progress_by_default(self, app):
        executor = HandoffExecutor(app=app)
        assert not executor.is_handoff_in_progress(1)
        assert executor.get_handoff_metadata(1) is None

    def test_flag_set_after_trigger(self, app):
        with app.app_context():
            executor = HandoffExecutor(app=app)
            agent = _make_agent()

            with patch.object(
                executor, "validate_preconditions"
            ) as mock_v, patch(
                "claude_headspace.services.handoff_executor.db"
            ) as mock_db, patch(
                "claude_headspace.services.tmux_bridge"
            ) as mock_tmux:
                mock_v.return_value = HandoffResult(success=True, message="OK")
                mock_db.session.get.return_value = agent
                mock_tmux.send_text.return_value = MagicMock(success=True)

                executor.trigger_handoff(1, reason="context_limit")

        metadata = executor.get_handoff_metadata(1)
        assert metadata is not None
        assert metadata["reason"] == "context_limit"
        assert "file_path" in metadata
        assert "triggered_at" in metadata


class TestContinueAfterStop:
    """Tests for continue_after_stop flow."""

    def test_no_handoff_in_progress(self, app):
        with app.app_context():
            executor = HandoffExecutor(app=app)
            agent = _make_agent()

            result = executor.continue_after_stop(agent)

        assert not result.success
        assert result.error_code == "no_handoff"

    def test_file_verification_failure(self, app):
        with app.app_context():
            executor = HandoffExecutor(app=app)
            agent = _make_agent()

            # Manually set the flag
            from claude_headspace.services.handoff_executor import (
                _handoff_in_progress,
                _handoff_lock,
            )

            with _handoff_lock:
                _handoff_in_progress[agent.id] = {
                    "file_path": "/nonexistent/file.md",
                    "reason": "test",
                    "triggered_at": "2026-01-01T00:00:00",
                }

            with patch(
                "claude_headspace.services.handoff_executor.db"
            ) as mock_db, patch.object(
                executor, "_broadcast_error"
            ), patch.object(executor, "_notify_error"):
                mock_db.session.get.return_value = agent
                result = executor.continue_after_stop(agent)

        assert not result.success
        assert result.error_code == "file_not_found"
        # Flag should be cleared on failure
        assert not executor.is_handoff_in_progress(agent.id)


class TestCompleteHandoff:
    """Tests for complete_handoff (core completion logic)."""

    def test_no_handoff_in_progress(self, app):
        with app.app_context():
            executor = HandoffExecutor(app=app)
            result = executor.complete_handoff(999)

        assert not result.success
        assert result.error_code == "no_handoff"

    def test_idempotent_when_already_completed(self, app, tmp_path):
        """complete_handoff returns success if Handoff record already exists."""
        with app.app_context():
            executor = HandoffExecutor(app=app)
            agent = _make_agent()

            # Write a valid handoff file
            handoff_file = tmp_path / "handoff.md"
            handoff_file.write_text("# Handoff\nSome content")

            from claude_headspace.services.handoff_executor import (
                _handoff_in_progress,
                _handoff_lock,
            )

            with _handoff_lock:
                _handoff_in_progress[agent.id] = {
                    "file_path": str(handoff_file),
                    "reason": "manual",
                    "triggered_at": "2026-01-01T00:00:00",
                }

            with patch(
                "claude_headspace.services.handoff_executor.db"
            ) as mock_db, patch(
                "claude_headspace.services.handoff_executor.Handoff"
            ) as mock_handoff:
                mock_db.session.get.return_value = agent
                # Simulate existing Handoff record
                mock_handoff.query.filter_by.return_value.first.return_value = (
                    MagicMock()
                )
                result = executor.complete_handoff(agent.id)

        assert result.success
        assert result.error_code == "already_completed"
        # Flag should be cleared
        assert not executor.is_handoff_in_progress(agent.id)

    def test_successful_completion(self, app, tmp_path):
        """complete_handoff creates record and successor, no shutdown."""
        with app.app_context():
            executor = HandoffExecutor(app=app)
            agent = _make_agent()

            # Write a valid handoff file
            handoff_file = tmp_path / "handoff.md"
            handoff_file.write_text("# Handoff\nDetailed context here")

            from claude_headspace.services.handoff_executor import (
                _handoff_in_progress,
                _handoff_lock,
            )

            with _handoff_lock:
                _handoff_in_progress[agent.id] = {
                    "file_path": str(handoff_file),
                    "reason": "manual",
                    "triggered_at": "2026-01-01T00:00:00",
                }

            mock_handoff_record = MagicMock()
            mock_handoff_record.id = 42

            with patch(
                "claude_headspace.services.handoff_executor.db"
            ) as mock_db, patch(
                "claude_headspace.services.handoff_executor.Handoff"
            ) as mock_handoff_cls, patch.object(
                executor, "_create_successor"
            ) as mock_create, patch.object(
                executor, "_broadcast_success"
            ):
                mock_db.session.get.return_value = agent
                # No existing Handoff record
                mock_handoff_cls.query.filter_by.return_value.first.return_value = None
                # Handoff() constructor returns our mock
                mock_handoff_cls.return_value = mock_handoff_record
                mock_create.return_value = HandoffResult(
                    success=True, message="Successor created"
                )

                result = executor.complete_handoff(agent.id)

        assert result.success
        assert result.message == "Handoff complete"
        # Flag should be cleared
        assert not executor.is_handoff_in_progress(agent.id)
        # Verify successor was created
        mock_create.assert_called_once_with(agent)
        # Verify DB record was added
        mock_db.session.add.assert_called_once_with(mock_handoff_record)
        mock_db.session.commit.assert_called_once()


class TestDeliverInjectionPrompt:
    """Tests for deliver_injection_prompt."""

    def test_no_predecessor(self, app):
        with app.app_context():
            executor = HandoffExecutor(app=app)
            agent = _make_agent(previous_agent_id=None)

            result = executor.deliver_injection_prompt(agent)

        assert not result.success
        assert result.error_code == "no_predecessor"

    def test_no_handoff_record(self, app):
        with app.app_context():
            executor = HandoffExecutor(app=app)
            agent = _make_agent(previous_agent_id=1)

            with patch(
                "claude_headspace.services.handoff_executor.Handoff"
            ) as mock_handoff:
                mock_handoff.query.filter_by.return_value.first.return_value = (
                    None
                )
                result = executor.deliver_injection_prompt(agent)

        assert not result.success
        assert result.error_code == "no_handoff_record"

    def test_no_tmux_pane(self, app):
        with app.app_context():
            executor = HandoffExecutor(app=app)
            agent = _make_agent(previous_agent_id=1, tmux_pane_id=None)

            handoff = MagicMock()
            handoff.injection_prompt = "Read the handoff doc"

            with patch(
                "claude_headspace.services.handoff_executor.Handoff"
            ) as mock_handoff:
                mock_handoff.query.filter_by.return_value.first.return_value = (
                    handoff
                )
                result = executor.deliver_injection_prompt(agent)

        assert not result.success
        assert result.error_code == "no_tmux_pane"

    def test_successful_delivery(self, app):
        with app.app_context():
            executor = HandoffExecutor(app=app)
            agent = _make_agent(previous_agent_id=1)

            handoff = MagicMock()
            handoff.id = 5
            handoff.injection_prompt = "Read the handoff doc at handoff.md"

            with patch(
                "claude_headspace.services.handoff_executor.Handoff"
            ) as mock_handoff, patch(
                "claude_headspace.services.tmux_bridge"
            ) as mock_tmux:
                mock_handoff.query.filter_by.return_value.first.return_value = (
                    handoff
                )
                mock_tmux.send_text.return_value = MagicMock(success=True)

                result = executor.deliver_injection_prompt(agent)

        assert result.success
        mock_tmux.send_text.assert_called_once_with(
            pane_id="%5",
            text="Read the handoff doc at handoff.md",
        )
