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
    """Tests for handoff file path generation — new ISO 8601 format."""

    def test_path_format_new(self, app):
        """New format: {YYYY-MM-DDTHH:MM:SS}_<insert-summary>_agent-id:{N}.md"""
        executor = HandoffExecutor(app=app)
        agent = _make_agent(agent_id=42)

        path = executor.generate_handoff_file_path(agent)

        # Path must be absolute
        assert os.path.isabs(path), f"Expected absolute path, got: {path}"
        assert "data/personas/developer-con-1/handoffs/" in path

        filename = os.path.basename(path)
        # Three sections separated by underscores
        parts = filename.split("_", 2)
        assert len(parts) == 3, f"Expected 3 underscore-separated parts, got: {filename}"

        # Section 1: ISO 8601 timestamp with separators
        timestamp = parts[0]
        assert "T" in timestamp
        assert "-" in timestamp.split("T")[0]  # Date has hyphens
        assert ":" in timestamp.split("T")[1]  # Time has colons

        # Section 2: <insert-summary> placeholder
        assert parts[1] == "<insert-summary>"

        # Section 3: agent-id:{N}.md
        assert parts[2] == "agent-id:42.md"

    def test_path_agent_id_no_padding(self, app):
        """Agent ID should NOT be zero-padded in new format."""
        executor = HandoffExecutor(app=app)
        agent = _make_agent(agent_id=7)

        path = executor.generate_handoff_file_path(agent)

        assert "agent-id:7.md" in path
        assert "00000007" not in path

    def test_path_large_agent_id(self, app):
        executor = HandoffExecutor(app=app)
        agent = _make_agent(agent_id=12345678)

        path = executor.generate_handoff_file_path(agent)

        assert "agent-id:12345678.md" in path

    def test_path_iso_timestamp_format(self, app):
        """Timestamp portion uses ISO 8601 with separators."""
        executor = HandoffExecutor(app=app)
        agent = _make_agent(agent_id=1137)

        path = executor.generate_handoff_file_path(agent)
        filename = os.path.basename(path)
        timestamp = filename.split("_")[0]

        # Should match YYYY-MM-DDTHH:MM:SS
        import re
        assert re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", timestamp)


class TestComposeHandoffInstruction:
    """Tests for handoff instruction composition."""

    def test_instruction_contains_file_path(self, app):
        executor = HandoffExecutor(app=app)
        file_path = "data/personas/dev/handoffs/2026-01-01T12:00:00_<insert-summary>_agent-id:1.md"

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
        """Handoff instruction should NOT tell the agent to /exit."""
        executor = HandoffExecutor(app=app)
        instruction = executor.compose_handoff_instruction("test.md")

        assert "/exit" not in instruction

    def test_instruction_contains_kebab_case_guidance(self, app):
        """Instruction must tell the agent to replace <insert-summary> with kebab-case."""
        executor = HandoffExecutor(app=app)
        instruction = executor.compose_handoff_instruction("test.md")

        assert "<insert-summary>" in instruction
        assert "kebab-case" in instruction
        assert "60" in instruction  # max 60 characters
        assert "underscore" in instruction.lower()  # no underscores

    def test_instruction_with_context(self, app):
        """Operator context is appended when provided."""
        executor = HandoffExecutor(app=app)
        instruction = executor.compose_handoff_instruction(
            "test.md", context="Focus on the auth module"
        )

        assert "Focus on the auth module" in instruction
        assert "ADDITIONAL CONTEXT" in instruction


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
                _handoff_in_progress_lock,
            )

            with _handoff_in_progress_lock:
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
                _handoff_in_progress_lock,
            )

            with _handoff_in_progress_lock:
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
                _handoff_in_progress_lock,
            )

            with _handoff_in_progress_lock:
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


class TestPollingGlobFallback:
    """Tests for _poll_for_handoff_file glob fallback (FR3)."""

    def test_glob_fallback_detects_renamed_file(self, app, tmp_path):
        """When exact path not found, glob matches renamed file."""
        executor = HandoffExecutor(app=app)
        agent = _make_agent(agent_id=42)

        # Create the handoff directory
        handoff_dir = tmp_path / "handoffs"
        handoff_dir.mkdir()

        # Generate the exact path (with placeholder)
        exact_path = str(
            handoff_dir / "2026-01-01T12:00:00_<insert-summary>_agent-id:42.md"
        )

        # The agent renamed the file (replaced the placeholder)
        renamed = handoff_dir / "2026-01-01T12:00:00_refactored-auth-module_agent-id:42.md"
        renamed.write_text("# Handoff\nContent here")

        # Set up handoff metadata
        from claude_headspace.services.handoff_executor import (
            _handoff_in_progress,
            _handoff_in_progress_lock,
        )

        with _handoff_in_progress_lock:
            _handoff_in_progress[42] = {
                "file_path": exact_path,
                "reason": "test",
                "triggered_at": "2026-01-01T00:00:00",
            }

        # Mock complete_handoff to verify it's called
        with patch.object(executor, "complete_handoff") as mock_complete:
            mock_complete.return_value = HandoffResult(
                success=True, message="OK"
            )

            # Run poll (with very short timeout)
            with patch(
                "claude_headspace.services.handoff_executor.POLL_TIMEOUT_SECONDS", 1
            ):
                executor._poll_for_handoff_file(42)

        mock_complete.assert_called_once_with(42)

        # Verify metadata was updated with the actual path
        metadata = executor.get_handoff_metadata(42)
        if metadata:
            assert "refactored-auth-module" in metadata["file_path"]

    def test_glob_fallback_logs_warning_multiple_matches(self, app, tmp_path, caplog):
        """Multiple glob matches log a warning."""
        executor = HandoffExecutor(app=app)

        handoff_dir = tmp_path / "handoffs"
        handoff_dir.mkdir()

        exact_path = str(
            handoff_dir / "2026-01-01T12:00:00_<insert-summary>_agent-id:42.md"
        )

        # Create two matching files
        (handoff_dir / "2026-01-01T12:00:00_first-summary_agent-id:42.md").write_text(
            "# First"
        )
        (handoff_dir / "2026-01-01T12:00:00_second-summary_agent-id:42.md").write_text(
            "# Second"
        )

        from claude_headspace.services.handoff_executor import (
            _handoff_in_progress,
            _handoff_in_progress_lock,
        )

        with _handoff_in_progress_lock:
            _handoff_in_progress[42] = {
                "file_path": exact_path,
                "reason": "test",
                "triggered_at": "2026-01-01T00:00:00",
            }

        with patch.object(executor, "complete_handoff") as mock_complete:
            mock_complete.return_value = HandoffResult(
                success=True, message="OK"
            )
            with patch(
                "claude_headspace.services.handoff_executor.POLL_TIMEOUT_SECONDS", 1
            ):
                import logging
                with caplog.at_level(logging.WARNING):
                    executor._poll_for_handoff_file(42)

        # Should still complete (uses first match)
        mock_complete.assert_called_once()
        # Should have logged a warning
        assert any("glob matched 2 files" in r.message for r in caplog.records)

    def test_exact_path_takes_precedence(self, app, tmp_path):
        """If exact path exists, glob fallback is not used."""
        executor = HandoffExecutor(app=app)

        handoff_dir = tmp_path / "handoffs"
        handoff_dir.mkdir()

        # Create the exact file (with placeholder name)
        exact_file = (
            handoff_dir / "2026-01-01T12:00:00_<insert-summary>_agent-id:42.md"
        )
        exact_file.write_text("# Handoff with placeholder name")
        exact_path = str(exact_file)

        from claude_headspace.services.handoff_executor import (
            _handoff_in_progress,
            _handoff_in_progress_lock,
        )

        with _handoff_in_progress_lock:
            _handoff_in_progress[42] = {
                "file_path": exact_path,
                "reason": "test",
                "triggered_at": "2026-01-01T00:00:00",
            }

        with patch.object(executor, "complete_handoff") as mock_complete:
            mock_complete.return_value = HandoffResult(
                success=True, message="OK"
            )
            with patch(
                "claude_headspace.services.handoff_executor.POLL_TIMEOUT_SECONDS", 1
            ):
                executor._poll_for_handoff_file(42)

        mock_complete.assert_called_once()
        # Metadata should still use the exact path
        metadata = executor.get_handoff_metadata(42)
        if metadata:
            assert "<insert-summary>" in metadata["file_path"]
