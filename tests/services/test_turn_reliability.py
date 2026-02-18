"""Tests for turn capture reliability — the two-commit pattern and recovery paths.

These tests verify the core guarantees of the three-tier reliability model:
1. Turns survive state transition failures (two-commit pattern)
2. Reconciler creates turns for unmatched JSONL entries
3. Recovered turns trigger lifecycle state transitions
4. Force reconciliation endpoint works
5. Idempotency: reconciler run twice produces no duplicates
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from claude_headspace.database import db
from claude_headspace.models.agent import Agent
from claude_headspace.models.project import Project
from claude_headspace.models.command import Command, CommandState
from claude_headspace.models.turn import Turn, TurnActor, TurnIntent
from claude_headspace.services.transcript_reader import TranscriptEntry
from claude_headspace.services.transcript_reconciler import (
    _apply_recovered_turn_lifecycle,
    _content_hash,
    get_reconcile_lock,
    reconcile_agent_session,
    reconcile_transcript_entries,
    remove_reconcile_lock,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def app_ctx(app):
    """Provide a Flask app context with database tables created."""
    with app.app_context():
        db.create_all()
        yield app
        db.session.rollback()
        db.drop_all()


@pytest.fixture
def project(app_ctx):
    p = Project(
        name="test-project",
        slug=f"test-project-{uuid4().hex[:8]}",
        path=f"/tmp/test-project-{uuid4().hex[:8]}",
    )
    db.session.add(p)
    db.session.flush()
    return p


@pytest.fixture
def agent(project):
    a = Agent(
        session_uuid=uuid4(),
        project_id=project.id,
        started_at=datetime.now(timezone.utc),
        last_seen_at=datetime.now(timezone.utc),
    )
    db.session.add(a)
    db.session.flush()
    return a


@pytest.fixture
def command(agent):
    c = Command(
        agent_id=agent.id,
        state=CommandState.PROCESSING,
        started_at=datetime.now(timezone.utc),
    )
    db.session.add(c)
    db.session.flush()
    return c


def _make_entry(role="user", content="Hello world", timestamp=None):
    return TranscriptEntry(
        type="assistant" if role == "assistant" else "user",
        role=role,
        content=content,
        timestamp=timestamp,
    )


# ---------------------------------------------------------------------------
# C1: Turn survives when _apply_recovered_turn_lifecycle fails
# ---------------------------------------------------------------------------


class TestTurnSurvivesLifecycleFailure:
    """Verify that turns committed before lifecycle call survive rollback."""

    def test_turn_survives_invalid_transition_error(self, app_ctx, agent, command):
        """Turn must persist even when state transition raises InvalidTransitionError."""
        command.state = CommandState.COMPLETE  # Terminal state — transitions will fail

        entries = [
            _make_entry(
                role="assistant",
                content="Would you like me to continue?",
                timestamp=datetime.now(timezone.utc),
            ),
        ]

        # detect_agent_intent will classify this as QUESTION
        with patch(
            "claude_headspace.services.transcript_reconciler.detect_agent_intent"
        ) as mock_detect:
            mock_result = MagicMock()
            mock_result.intent = TurnIntent.QUESTION
            mock_result.confidence = 0.9
            mock_detect.return_value = mock_result

            result = reconcile_transcript_entries(agent, command, entries)

        # Turn was created
        assert len(result["created"]) == 1
        turn_id = result["created"][0]

        # Turn survives in the database despite lifecycle failure
        turn = db.session.get(Turn, turn_id)
        assert turn is not None
        assert turn.intent == TurnIntent.QUESTION
        assert "Would you like me to continue?" in turn.text

    def test_turn_survives_generic_exception_in_lifecycle(self, app_ctx, agent, command):
        """Turn must persist even when lifecycle raises a generic exception."""
        entries = [
            _make_entry(
                role="assistant",
                content="I found a critical bug in the authentication module.",
                timestamp=datetime.now(timezone.utc),
            ),
        ]

        with patch(
            "claude_headspace.services.transcript_reconciler.detect_agent_intent"
        ) as mock_detect:
            mock_result = MagicMock()
            mock_result.intent = TurnIntent.COMPLETION
            mock_result.confidence = 0.95
            mock_detect.return_value = mock_result

            # Force lifecycle to raise — the exception propagates out of
            # reconcile_transcript_entries but the turn was committed before
            # the lifecycle call, so it should survive.
            with patch(
                "claude_headspace.services.transcript_reconciler._apply_recovered_turn_lifecycle",
                side_effect=Exception("DB connection lost"),
            ):
                try:
                    result = reconcile_transcript_entries(agent, command, entries)
                except Exception:
                    # Exception propagates — that's expected.
                    # The critical thing is the turn survived.
                    pass

        # Turn was committed BEFORE lifecycle was called — verify it's in the DB.
        turns = Turn.query.filter_by(command_id=command.id).all()
        agent_turns = [t for t in turns if t.actor == TurnActor.AGENT]
        assert len(agent_turns) == 1
        assert "critical bug" in agent_turns[0].text


# ---------------------------------------------------------------------------
# R2-C1: No duplicate turns for COMPLETION/END_OF_COMMAND via reconciler
# ---------------------------------------------------------------------------


class TestNoDuplicateTurnOnCompletion:
    """Verify reconciler COMPLETION path doesn't create a duplicate turn."""

    def test_completion_passes_empty_agent_text(self, app_ctx, agent, command):
        """complete_command must be called with empty agent_text — recovered turn already exists."""
        entries = [
            _make_entry(
                role="assistant",
                content="All tasks completed successfully. The feature is ready.",
                timestamp=datetime.now(timezone.utc),
            ),
        ]

        with patch(
            "claude_headspace.services.transcript_reconciler.detect_agent_intent"
        ) as mock_detect, patch(
            "claude_headspace.services.transcript_reconciler._apply_recovered_turn_lifecycle"
        ) as mock_lifecycle:
            mock_result = MagicMock()
            mock_result.intent = TurnIntent.COMPLETION
            mock_result.confidence = 0.95
            mock_detect.return_value = mock_result

            result = reconcile_transcript_entries(agent, command, entries)

        # One turn was created by the reconciler
        assert len(result["created"]) == 1

        # Lifecycle was called with the recovered turn
        mock_lifecycle.assert_called_once()
        call_args = mock_lifecycle.call_args
        assert call_args[0][2].intent == TurnIntent.COMPLETION

        # Verify EXACTLY one agent turn exists (the reconciler-created one)
        all_turns = Turn.query.filter_by(command_id=command.id).all()
        agent_turns = [t for t in all_turns if t.actor == TurnActor.AGENT]
        assert len(agent_turns) == 1, (
            f"Expected exactly 1 agent turn, got {len(agent_turns)}."
        )

    def test_apply_lifecycle_sets_full_output_without_duplicate(self, app_ctx, agent, command):
        """_apply_recovered_turn_lifecycle must set full_output but pass agent_text='' to complete_command."""
        from flask import current_app

        turn = Turn(
            command_id=command.id,
            actor=TurnActor.AGENT,
            intent=TurnIntent.COMPLETION,
            text="Implementation complete. All tests pass.",
            timestamp=datetime.now(timezone.utc),
        )
        db.session.add(turn)
        db.session.commit()

        intent_result = MagicMock()
        intent_result.intent = TurnIntent.COMPLETION
        intent_result.confidence = 0.95

        # Replace the lifecycle manager with a mock in the real app extensions
        mock_lifecycle = MagicMock()
        original = current_app.extensions.get("command_lifecycle")
        current_app.extensions["command_lifecycle"] = mock_lifecycle
        try:
            _apply_recovered_turn_lifecycle(agent, command, turn, intent_result)
        finally:
            if original is not None:
                current_app.extensions["command_lifecycle"] = original

        # complete_command should have been called with agent_text=""
        mock_lifecycle.complete_command.assert_called_once()
        call_kwargs = mock_lifecycle.complete_command.call_args
        assert call_kwargs[1].get("agent_text") == "", \
            f"complete_command should receive agent_text='' to prevent duplicate turn, got: {call_kwargs}"

        # full_output should be set directly on the command (not by complete_command)
        assert command.full_output == "Implementation complete. All tests pass."


# ---------------------------------------------------------------------------
# C2: reconcile_agent_session feeds turns into lifecycle
# ---------------------------------------------------------------------------


class TestReconcileAgentSessionLifecycle:
    """Verify reconcile_agent_session integrates with lifecycle."""

    def test_session_reconcile_calls_lifecycle_for_question(self, app_ctx, agent, command):
        """reconcile_agent_session should call _apply_recovered_turn_lifecycle."""
        agent.transcript_path = "/tmp/fake_transcript.jsonl"

        entries = [
            _make_entry(
                role="assistant",
                content="Unique question text for lifecycle test",
                timestamp=datetime.now(timezone.utc),
            ),
        ]

        # Patch at the source module where the import happens inside the function
        with patch(
            "claude_headspace.services.transcript_reader.read_new_entries_from_position",
            return_value=(entries, 100),
        ), patch(
            "claude_headspace.services.transcript_reconciler.detect_agent_intent"
        ) as mock_detect, patch(
            "claude_headspace.services.transcript_reconciler._apply_recovered_turn_lifecycle"
        ) as mock_lifecycle:
            mock_result = MagicMock()
            mock_result.intent = TurnIntent.QUESTION
            mock_result.confidence = 0.9
            mock_detect.return_value = mock_result

            result = reconcile_agent_session(agent)

        assert len(result["created"]) == 1
        # Verify lifecycle was called
        mock_lifecycle.assert_called_once()
        call_args = mock_lifecycle.call_args
        assert call_args[0][0] == agent    # agent
        assert call_args[0][1] == command  # latest_command


# ---------------------------------------------------------------------------
# H3: Dual-hash double-matching prevention
# ---------------------------------------------------------------------------


class TestDualHashNoDoubleMatch:
    """Verify a turn can only be matched once despite having two hash keys."""

    def test_same_turn_not_matched_twice(self, app_ctx, agent, command):
        """When a turn matches via new hash, the legacy hash should be removed."""
        now = datetime.now(timezone.utc)

        # Create a turn with text that has different new vs legacy hashes
        long_text = "a" * 250  # > 200 chars, so new_hash != legacy_hash
        turn = Turn(
            command_id=command.id,
            actor=TurnActor.AGENT,
            intent=TurnIntent.PROGRESS,
            text=long_text,
            timestamp=now,
        )
        db.session.add(turn)
        db.session.flush()

        # Entry 1 matches via full hash
        entry1 = _make_entry(
            role="assistant",
            content=long_text,
            timestamp=now + timedelta(seconds=1),
        )
        # Entry 2 has same first 200 chars but different suffix
        # It would match the legacy hash if not cleaned up
        different_text = "a" * 200 + "b" * 50
        entry2 = _make_entry(
            role="assistant",
            content=different_text,
            timestamp=now + timedelta(seconds=2),
        )

        result = reconcile_transcript_entries(agent, command, [entry1, entry2])

        # Entry 1 matched the existing turn (updated timestamp)
        assert len(result["updated"]) == 1
        # Entry 2 should create a new turn (not double-match the existing one)
        assert len(result["created"]) == 1


# ---------------------------------------------------------------------------
# Idempotency: reconciler run twice produces no duplicates
# ---------------------------------------------------------------------------


class TestReconcilerIdempotency:
    """Verify running reconciliation twice doesn't create duplicate turns."""

    def test_reconcile_twice_no_duplicates(self, app_ctx, agent, command):
        """Running reconcile_transcript_entries twice with same data creates turns only once."""
        entries = [
            _make_entry(
                role="assistant",
                content="First unique message for idempotency test",
                timestamp=datetime.now(timezone.utc),
            ),
            _make_entry(
                role="user",
                content="Second unique message for idempotency test",
                timestamp=datetime.now(timezone.utc) + timedelta(seconds=1),
            ),
        ]

        # First run — should create turns
        result1 = reconcile_transcript_entries(agent, command, entries)
        assert len(result1["created"]) == 2

        # Second run — same entries, should match existing turns (update timestamps)
        result2 = reconcile_transcript_entries(agent, command, entries)
        assert len(result2["created"]) == 0


# ---------------------------------------------------------------------------
# M1: Lock cleanup
# ---------------------------------------------------------------------------


class TestReconcileLockCleanup:
    """Verify per-agent locks can be cleaned up."""

    def test_remove_reconcile_lock(self):
        """remove_reconcile_lock should remove the lock for the given agent."""
        lock = get_reconcile_lock(999)
        assert lock is not None

        remove_reconcile_lock(999)

        # Getting the lock again should create a new one
        lock2 = get_reconcile_lock(999)
        assert lock2 is not lock  # Different object

        # Cleanup
        remove_reconcile_lock(999)

    def test_remove_nonexistent_lock_is_noop(self):
        """Removing a lock that doesn't exist should not raise."""
        remove_reconcile_lock(99999)  # Should not raise


# ---------------------------------------------------------------------------
# Force reconciliation endpoint
# ---------------------------------------------------------------------------


class TestReconcileEndpoint:
    """Test the POST /api/agents/<id>/reconcile endpoint."""

    def test_reconcile_endpoint_agent_not_found(self, app_ctx):
        """Should return 404 for non-existent agent."""
        app = app_ctx
        # Blueprint already registered by app factory
        with app.test_client() as client:
            resp = client.post("/api/agents/99999/reconcile")
            assert resp.status_code == 404

    def test_reconcile_endpoint_lock_contention(self, app_ctx, agent):
        """Should return 409 when reconciliation is already in progress."""
        app = app_ctx

        # Pre-acquire the lock
        lock = get_reconcile_lock(agent.id)
        lock.acquire()

        try:
            with app.test_client() as client:
                resp = client.post(f"/api/agents/{agent.id}/reconcile")
                assert resp.status_code == 409
                data = resp.get_json()
                assert data["status"] == "busy"
                assert data["created"] == 0
        finally:
            lock.release()
            remove_reconcile_lock(agent.id)
