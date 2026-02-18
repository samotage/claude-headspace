"""Tests for transcript reconciler service."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from claude_headspace.database import db
from claude_headspace.models.agent import Agent
from claude_headspace.models.project import Project
from claude_headspace.models.task import Task, TaskState
from claude_headspace.models.turn import Turn, TurnActor, TurnIntent
from claude_headspace.services.transcript_reader import TranscriptEntry
from claude_headspace.services.transcript_reconciler import (
    _content_hash,
    _legacy_content_hash,
    broadcast_reconciliation,
    reconcile_agent_session,
    reconcile_transcript_entries,
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
    """Create a test Project record."""
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
    """Create a test Agent record."""
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
def task(agent):
    """Create a test Task record."""
    t = Task(
        agent_id=agent.id,
        state=TaskState.PROCESSING,
        started_at=datetime.now(timezone.utc),
    )
    db.session.add(t)
    db.session.flush()
    return t


def _make_entry(role="user", content="Hello world", timestamp=None):
    """Create a TranscriptEntry for testing."""
    return TranscriptEntry(
        type="assistant" if role == "assistant" else "user",
        role=role,
        content=content,
        timestamp=timestamp,
    )


# ---------------------------------------------------------------------------
# Tests for _content_hash
# ---------------------------------------------------------------------------


class TestContentHash:
    """Tests for the _content_hash helper."""

    def test_deterministic(self):
        """Same input produces same hash."""
        h1 = _content_hash("user", "hello world")
        h2 = _content_hash("user", "hello world")
        assert h1 == h2

    def test_different_actor_different_hash(self):
        """Different actors produce different hashes for same text."""
        h_user = _content_hash("user", "hello world")
        h_agent = _content_hash("agent", "hello world")
        assert h_user != h_agent

    def test_different_text_different_hash(self):
        """Different text produces different hashes."""
        h1 = _content_hash("user", "hello")
        h2 = _content_hash("user", "goodbye")
        assert h1 != h2

    def test_hash_is_16_chars(self):
        """Hash output is truncated to 16 hex characters."""
        h = _content_hash("user", "test")
        assert len(h) == 16

    def test_case_insensitive(self):
        """Hash normalizes text to lowercase."""
        h1 = _content_hash("user", "Hello World")
        h2 = _content_hash("user", "hello world")
        assert h1 == h2

    def test_uses_full_content(self):
        """Hash uses full content (not truncated to 200 chars)."""
        long_text = "a" * 300
        different_suffix = "a" * 200 + "b" * 100
        h1 = _content_hash("user", long_text)
        h2 = _content_hash("user", different_suffix)
        assert h1 != h2  # Full content hash differentiates these

    def test_legacy_hash_truncates_to_200_chars(self):
        """Legacy hash uses only first 200 characters for migration compatibility."""
        long_text = "a" * 300
        different_suffix = "a" * 200 + "b" * 100
        h1 = _legacy_content_hash("user", long_text)
        h2 = _legacy_content_hash("user", different_suffix)
        assert h1 == h2

    def test_strips_whitespace(self):
        """Hash strips leading/trailing whitespace from text."""
        h1 = _content_hash("user", "  hello  ")
        h2 = _content_hash("user", "hello")
        assert h1 == h2


# ---------------------------------------------------------------------------
# Tests for reconcile_transcript_entries
# ---------------------------------------------------------------------------


class TestReconcileEmptyEntries:
    """Test reconciliation with empty/no entries."""

    def test_empty_entries_returns_empty_result(self, app_ctx, agent, task):
        """Empty entries list returns empty result with no DB changes."""
        result = reconcile_transcript_entries(agent, task, [])
        assert result == {"updated": [], "created": []}

    def test_none_content_entries_skipped(self, app_ctx, agent, task):
        """Entries with None content are skipped."""
        entry = TranscriptEntry(type="user", role="user", content=None)
        result = reconcile_transcript_entries(agent, task, [entry])
        assert result == {"updated": [], "created": []}

    def test_whitespace_only_content_entries_skipped(self, app_ctx, agent, task):
        """Entries with whitespace-only content are skipped."""
        entry = _make_entry(role="user", content="   \n\t  ")
        result = reconcile_transcript_entries(agent, task, [entry])
        assert result == {"updated": [], "created": []}

    def test_empty_string_content_entries_skipped(self, app_ctx, agent, task):
        """Entries with empty string content are skipped."""
        entry = _make_entry(role="user", content="")
        result = reconcile_transcript_entries(agent, task, [entry])
        assert result == {"updated": [], "created": []}


class TestReconcileExactMatch:
    """Test reconciliation when entries match existing turns."""

    def test_exact_match_updates_timestamp(self, app_ctx, agent, task):
        """Matching entry updates the turn's timestamp to the JSONL timestamp."""
        now = datetime.now(timezone.utc)
        server_ts = now - timedelta(seconds=5)
        jsonl_ts = now - timedelta(seconds=3)

        # Create existing turn (simulating hook-created turn)
        turn = Turn(
            task_id=task.id,
            actor=TurnActor.USER,
            intent=TurnIntent.COMMAND,
            text="Fix the login bug",
            timestamp=server_ts,
            timestamp_source="server",
        )
        db.session.add(turn)
        db.session.flush()
        turn_id = turn.id

        # Reconcile with matching JSONL entry
        entry = _make_entry(role="user", content="Fix the login bug", timestamp=jsonl_ts)
        result = reconcile_transcript_entries(agent, task, [entry])

        assert len(result["updated"]) == 1
        assert len(result["created"]) == 0

        updated_turn_id, old_ts, new_ts = result["updated"][0]
        assert updated_turn_id == turn_id
        assert old_ts == server_ts
        assert new_ts == jsonl_ts

        # Verify the turn record was updated
        refreshed = db.session.get(Turn, turn_id)
        assert refreshed.timestamp == jsonl_ts
        assert refreshed.timestamp_source == "jsonl"
        assert refreshed.jsonl_entry_hash is not None

    def test_match_with_same_timestamp_no_update(self, app_ctx, agent, task):
        """When timestamps match exactly, no update is recorded."""
        now = datetime.now(timezone.utc)
        exact_ts = now - timedelta(seconds=5)

        turn = Turn(
            task_id=task.id,
            actor=TurnActor.USER,
            intent=TurnIntent.COMMAND,
            text="Deploy to staging",
            timestamp=exact_ts,
            timestamp_source="server",
        )
        db.session.add(turn)
        db.session.flush()

        entry = _make_entry(role="user", content="Deploy to staging", timestamp=exact_ts)
        result = reconcile_transcript_entries(agent, task, [entry])

        assert len(result["updated"]) == 0
        assert len(result["created"]) == 0

    def test_match_without_jsonl_timestamp_records_hash(self, app_ctx, agent, task):
        """Matching entry without timestamp records the hash for dedup."""
        now = datetime.now(timezone.utc)

        turn = Turn(
            task_id=task.id,
            actor=TurnActor.USER,
            intent=TurnIntent.COMMAND,
            text="Run the tests",
            timestamp=now,
            timestamp_source="server",
            jsonl_entry_hash=None,
        )
        db.session.add(turn)
        db.session.flush()
        turn_id = turn.id

        entry = _make_entry(role="user", content="Run the tests", timestamp=None)
        result = reconcile_transcript_entries(agent, task, [entry])

        assert len(result["updated"]) == 0
        assert len(result["created"]) == 0

        refreshed = db.session.get(Turn, turn_id)
        assert refreshed.jsonl_entry_hash is not None

    def test_match_without_timestamp_preserves_existing_hash(self, app_ctx, agent, task):
        """If turn already has a hash, matching without timestamp doesn't overwrite it."""
        now = datetime.now(timezone.utc)
        existing_hash = "abcdef1234567890"

        turn = Turn(
            task_id=task.id,
            actor=TurnActor.USER,
            intent=TurnIntent.COMMAND,
            text="Check status",
            timestamp=now,
            timestamp_source="server",
            jsonl_entry_hash=existing_hash,
        )
        db.session.add(turn)
        db.session.flush()
        turn_id = turn.id

        entry = _make_entry(role="user", content="Check status", timestamp=None)
        result = reconcile_transcript_entries(agent, task, [entry])

        refreshed = db.session.get(Turn, turn_id)
        assert refreshed.jsonl_entry_hash == existing_hash


class TestReconcileNoMatch:
    """Test reconciliation when entries don't match existing turns."""

    def test_no_match_creates_new_turn(self, app_ctx, agent, task):
        """Unmatched entry creates a new Turn record."""
        jsonl_ts = datetime.now(timezone.utc) - timedelta(seconds=2)

        entry = _make_entry(role="user", content="Write unit tests", timestamp=jsonl_ts)
        result = reconcile_transcript_entries(agent, task, [entry])

        assert len(result["updated"]) == 0
        assert len(result["created"]) == 1

        new_turn_id = result["created"][0]
        new_turn = db.session.get(Turn, new_turn_id)
        assert new_turn is not None
        assert new_turn.text == "Write unit tests"
        assert new_turn.actor == TurnActor.USER
        assert new_turn.intent == TurnIntent.COMMAND
        assert new_turn.timestamp == jsonl_ts
        assert new_turn.timestamp_source == "jsonl"
        assert new_turn.task_id == task.id
        assert new_turn.jsonl_entry_hash is not None

    def test_no_match_agent_entry_creates_agent_turn(self, app_ctx, agent, task):
        """Unmatched agent entry creates a Turn with AGENT actor and PROGRESS intent."""
        jsonl_ts = datetime.now(timezone.utc)

        entry = _make_entry(role="assistant", content="I will fix this now", timestamp=jsonl_ts)
        result = reconcile_transcript_entries(agent, task, [entry])

        assert len(result["created"]) == 1
        new_turn = db.session.get(Turn, result["created"][0])
        assert new_turn.actor == TurnActor.AGENT
        assert new_turn.intent == TurnIntent.PROGRESS

    def test_no_match_without_timestamp_uses_server_time(self, app_ctx, agent, task):
        """Unmatched entry without timestamp uses server time."""
        before = datetime.now(timezone.utc)

        entry = _make_entry(role="user", content="Something new", timestamp=None)
        result = reconcile_transcript_entries(agent, task, [entry])

        after = datetime.now(timezone.utc)

        assert len(result["created"]) == 1
        new_turn = db.session.get(Turn, result["created"][0])
        assert new_turn.timestamp_source == "server"
        assert before <= new_turn.timestamp <= after

    def test_no_match_strips_content_whitespace(self, app_ctx, agent, task):
        """New turns store stripped content."""
        entry = _make_entry(
            role="user",
            content="  padded content  ",
            timestamp=datetime.now(timezone.utc),
        )
        result = reconcile_transcript_entries(agent, task, [entry])

        new_turn = db.session.get(Turn, result["created"][0])
        assert new_turn.text == "padded content"


class TestReconcileMultipleEntries:
    """Test reconciliation with multiple entries (mix of matches and new)."""

    def test_mixed_matches_and_new_entries(self, app_ctx, agent, task):
        """Multiple entries: some match existing turns, some create new ones."""
        now = datetime.now(timezone.utc)
        server_ts = now - timedelta(seconds=10)
        jsonl_ts = now - timedelta(seconds=8)

        # Create existing turn that will match
        existing_turn = Turn(
            task_id=task.id,
            actor=TurnActor.USER,
            intent=TurnIntent.COMMAND,
            text="Existing command",
            timestamp=server_ts,
            timestamp_source="server",
        )
        db.session.add(existing_turn)
        db.session.flush()
        existing_id = existing_turn.id

        entries = [
            _make_entry(role="user", content="Existing command", timestamp=jsonl_ts),
            _make_entry(role="assistant", content="New agent response", timestamp=now),
            _make_entry(role="user", content="Another new command", timestamp=now),
        ]
        result = reconcile_transcript_entries(agent, task, entries)

        assert len(result["updated"]) == 1
        assert result["updated"][0][0] == existing_id
        assert len(result["created"]) == 2

    def test_multiple_new_entries(self, app_ctx, agent, task):
        """All entries are new (no existing turns to match)."""
        now = datetime.now(timezone.utc)

        entries = [
            _make_entry(role="user", content="First command", timestamp=now),
            _make_entry(role="assistant", content="First response", timestamp=now),
            _make_entry(role="user", content="Second command", timestamp=now),
        ]
        result = reconcile_transcript_entries(agent, task, entries)

        assert len(result["updated"]) == 0
        assert len(result["created"]) == 3

    def test_skips_empty_among_valid(self, app_ctx, agent, task):
        """Empty/whitespace entries are skipped while valid entries are processed."""
        now = datetime.now(timezone.utc)

        entries = [
            _make_entry(role="user", content="Valid command", timestamp=now),
            _make_entry(role="user", content="", timestamp=now),
            _make_entry(role="user", content="   ", timestamp=now),
            TranscriptEntry(type="user", role="user", content=None, timestamp=now),
            _make_entry(role="assistant", content="Valid response", timestamp=now),
        ]
        result = reconcile_transcript_entries(agent, task, entries)

        assert len(result["created"]) == 2
        assert len(result["updated"]) == 0

    def test_commits_only_when_changes_exist(self, app_ctx, agent, task):
        """DB commit is issued only when there are updates or creates."""
        now = datetime.now(timezone.utc)
        exact_ts = now - timedelta(seconds=5)

        # Create a turn that will match exactly (same timestamp)
        turn = Turn(
            task_id=task.id,
            actor=TurnActor.USER,
            intent=TurnIntent.COMMAND,
            text="Same timestamp",
            timestamp=exact_ts,
            timestamp_source="server",
        )
        db.session.add(turn)
        db.session.flush()

        # This entry matches but timestamp is identical, so no update
        entry = _make_entry(role="user", content="Same timestamp", timestamp=exact_ts)

        with patch.object(db.session, "commit") as mock_commit:
            result = reconcile_transcript_entries(agent, task, [entry])
            mock_commit.assert_not_called()

        assert len(result["updated"]) == 0
        assert len(result["created"]) == 0


class TestReconcileOldTurnsNotMatched:
    """Test that turns outside the match window are not considered."""

    def test_old_turns_outside_window_not_matched(self, app_ctx, agent, task):
        """Turns older than MATCH_WINDOW_SECONDS (120s) are not matched, creating new turns."""
        old_ts = datetime.now(timezone.utc) - timedelta(seconds=150)

        turn = Turn(
            task_id=task.id,
            actor=TurnActor.USER,
            intent=TurnIntent.COMMAND,
            text="Old command",
            timestamp=old_ts,
            timestamp_source="server",
        )
        db.session.add(turn)
        db.session.flush()

        # Entry has same content but the existing turn is outside the match window
        now = datetime.now(timezone.utc)
        entry = _make_entry(role="user", content="Old command", timestamp=now)
        result = reconcile_transcript_entries(agent, task, [entry])

        # Should create new turn since the old one is outside the window
        assert len(result["created"]) == 1
        assert len(result["updated"]) == 0


# ---------------------------------------------------------------------------
# Tests for broadcast_reconciliation
# ---------------------------------------------------------------------------


class TestBroadcastReconciliationEmpty:
    """Test broadcast_reconciliation with empty results."""

    @patch("claude_headspace.services.broadcaster.get_broadcaster")
    def test_empty_result_no_broadcasts(self, mock_get_broadcaster):
        """Empty reconciliation result sends no broadcasts."""
        agent = MagicMock()
        agent.id = 1
        agent.project_id = 10

        result = {"updated": [], "created": []}
        broadcast_reconciliation(agent, result)

        mock_get_broadcaster.assert_not_called()


class TestBroadcastReconciliationUpdated:
    """Test broadcast_reconciliation for updated turns."""

    @patch("claude_headspace.services.broadcaster.get_broadcaster")
    def test_broadcasts_turn_updated_for_timestamp_corrections(self, mock_get_broadcaster):
        """Updated turns trigger turn_updated broadcast events."""
        mock_broadcaster = MagicMock()
        mock_get_broadcaster.return_value = mock_broadcaster

        agent = MagicMock()
        agent.id = 1
        agent.project_id = 10

        old_ts = datetime(2026, 2, 15, 10, 0, 0, tzinfo=timezone.utc)
        new_ts = datetime(2026, 2, 15, 10, 0, 2, tzinfo=timezone.utc)

        result = {
            "updated": [(42, old_ts, new_ts)],
            "created": [],
        }
        broadcast_reconciliation(agent, result)

        mock_broadcaster.broadcast.assert_called_once_with(
            "turn_updated",
            {
                "agent_id": 1,
                "project_id": 10,
                "turn_id": 42,
                "timestamp": new_ts.isoformat(),
                "update_type": "timestamp_correction",
            },
        )

    @patch("claude_headspace.services.broadcaster.get_broadcaster")
    def test_broadcasts_multiple_updated_turns(self, mock_get_broadcaster):
        """Multiple updated turns each get a separate broadcast."""
        mock_broadcaster = MagicMock()
        mock_get_broadcaster.return_value = mock_broadcaster

        agent = MagicMock()
        agent.id = 1
        agent.project_id = 10

        ts1_old = datetime(2026, 2, 15, 10, 0, 0, tzinfo=timezone.utc)
        ts1_new = datetime(2026, 2, 15, 10, 0, 1, tzinfo=timezone.utc)
        ts2_old = datetime(2026, 2, 15, 10, 0, 5, tzinfo=timezone.utc)
        ts2_new = datetime(2026, 2, 15, 10, 0, 6, tzinfo=timezone.utc)

        result = {
            "updated": [(42, ts1_old, ts1_new), (43, ts2_old, ts2_new)],
            "created": [],
        }
        broadcast_reconciliation(agent, result)

        assert mock_broadcaster.broadcast.call_count == 2

    @patch("claude_headspace.services.broadcaster.get_broadcaster")
    def test_updated_broadcast_exception_does_not_propagate(self, mock_get_broadcaster):
        """Broadcast exceptions for updated turns are caught and logged."""
        mock_broadcaster = MagicMock()
        mock_broadcaster.broadcast.side_effect = RuntimeError("SSE error")
        mock_get_broadcaster.return_value = mock_broadcaster

        agent = MagicMock()
        agent.id = 1
        agent.project_id = 10

        ts_old = datetime(2026, 2, 15, 10, 0, 0, tzinfo=timezone.utc)
        ts_new = datetime(2026, 2, 15, 10, 0, 1, tzinfo=timezone.utc)

        result = {"updated": [(42, ts_old, ts_new)], "created": []}

        # Should not raise
        broadcast_reconciliation(agent, result)


class TestBroadcastReconciliationCreated:
    """Test broadcast_reconciliation for created turns."""

    @patch("claude_headspace.services.transcript_reconciler.db")
    @patch("claude_headspace.services.broadcaster.get_broadcaster")
    def test_broadcasts_turn_created_for_new_turns(self, mock_get_broadcaster, mock_db):
        """Created turns trigger turn_created broadcast events."""
        mock_broadcaster = MagicMock()
        mock_get_broadcaster.return_value = mock_broadcaster

        ts = datetime(2026, 2, 15, 10, 0, 0, tzinfo=timezone.utc)

        mock_task = MagicMock()
        mock_task.instruction = "Do something"

        mock_turn = MagicMock()
        mock_turn.text = "Hello world"
        mock_turn.actor.value = "user"
        mock_turn.intent.value = "command"
        mock_turn.task_id = 5
        mock_turn.task = mock_task
        mock_turn.id = 99
        mock_turn.question_source_type = None
        mock_turn.timestamp.isoformat.return_value = ts.isoformat()

        mock_db.session.get.return_value = mock_turn

        agent = MagicMock()
        agent.id = 1
        agent.project_id = 10

        result = {"updated": [], "created": [99]}
        broadcast_reconciliation(agent, result)

        mock_broadcaster.broadcast.assert_called_once_with(
            "turn_created",
            {
                "agent_id": 1,
                "project_id": 10,
                "text": "Hello world",
                "actor": "user",
                "intent": "command",
                "task_id": 5,
                "task_instruction": "Do something",
                "turn_id": 99,
                "question_source_type": None,
                "timestamp": ts.isoformat(),
            },
        )

    @patch("claude_headspace.services.transcript_reconciler.db")
    @patch("claude_headspace.services.broadcaster.get_broadcaster")
    def test_skips_broadcast_if_turn_not_found(self, mock_get_broadcaster, mock_db):
        """If the created turn is not found in DB, broadcast is skipped."""
        mock_broadcaster = MagicMock()
        mock_get_broadcaster.return_value = mock_broadcaster

        mock_db.session.get.return_value = None

        agent = MagicMock()
        agent.id = 1
        agent.project_id = 10

        result = {"updated": [], "created": [999]}
        broadcast_reconciliation(agent, result)

        mock_broadcaster.broadcast.assert_not_called()

    @patch("claude_headspace.services.transcript_reconciler.db")
    @patch("claude_headspace.services.broadcaster.get_broadcaster")
    def test_created_broadcast_exception_does_not_propagate(self, mock_get_broadcaster, mock_db):
        """Broadcast exceptions for created turns are caught and logged."""
        mock_broadcaster = MagicMock()
        mock_broadcaster.broadcast.side_effect = RuntimeError("SSE error")
        mock_get_broadcaster.return_value = mock_broadcaster

        mock_turn = MagicMock()
        mock_db.session.get.return_value = mock_turn

        agent = MagicMock()
        agent.id = 1
        agent.project_id = 10

        result = {"updated": [], "created": [42]}

        # Should not raise
        broadcast_reconciliation(agent, result)

    @patch("claude_headspace.services.broadcaster.get_broadcaster")
    def test_broadcaster_not_available_does_not_raise(self, mock_get_broadcaster):
        """If get_broadcaster raises, the exception is caught and logged."""
        mock_get_broadcaster.side_effect = RuntimeError("No broadcaster")

        agent = MagicMock()
        agent.id = 1
        agent.project_id = 10

        result = {"updated": [(42, datetime.now(timezone.utc), datetime.now(timezone.utc))], "created": []}

        # Should not raise
        broadcast_reconciliation(agent, result)


class TestBroadcastReconciliationMixed:
    """Test broadcast_reconciliation with both updated and created turns."""

    @patch("claude_headspace.services.transcript_reconciler.db")
    @patch("claude_headspace.services.broadcaster.get_broadcaster")
    def test_broadcasts_both_updated_and_created(self, mock_get_broadcaster, mock_db):
        """Mixed results broadcast both turn_updated and turn_created events."""
        mock_broadcaster = MagicMock()
        mock_get_broadcaster.return_value = mock_broadcaster

        ts_old = datetime(2026, 2, 15, 10, 0, 0, tzinfo=timezone.utc)
        ts_new = datetime(2026, 2, 15, 10, 0, 1, tzinfo=timezone.utc)

        mock_turn = MagicMock()
        mock_turn.text = "New turn"
        mock_turn.actor.value = "agent"
        mock_turn.intent.value = "progress"
        mock_turn.task_id = 5
        mock_turn.id = 99
        mock_turn.timestamp.isoformat.return_value = ts_new.isoformat()

        mock_db.session.get.return_value = mock_turn

        agent = MagicMock()
        agent.id = 1
        agent.project_id = 10

        result = {
            "updated": [(42, ts_old, ts_new)],
            "created": [99],
        }
        broadcast_reconciliation(agent, result)

        assert mock_broadcaster.broadcast.call_count == 2

        # First call should be turn_updated
        first_call = mock_broadcaster.broadcast.call_args_list[0]
        assert first_call[0][0] == "turn_updated"

        # Second call should be turn_created
        second_call = mock_broadcaster.broadcast.call_args_list[1]
        assert second_call[0][0] == "turn_created"


# ---------------------------------------------------------------------------
# Tests for reconcile_agent_session
# ---------------------------------------------------------------------------


class TestReconcileAgentSession:
    """Tests for full-session reconciliation at session end."""

    def test_reconcile_agent_session_no_transcript(self, app_ctx, agent, task):
        """Agent with no transcript_path returns empty result."""
        agent.transcript_path = None
        result = reconcile_agent_session(agent)
        assert result == {"updated": [], "created": []}

    @patch("claude_headspace.services.transcript_reader.read_new_entries_from_position")
    def test_reconcile_agent_session_creates_missing_turns(self, mock_read, app_ctx, agent, task):
        """Missing JSONL entries should be created as new turns."""
        agent.transcript_path = "/tmp/test-transcript.jsonl"
        jsonl_ts = datetime.now(timezone.utc) - timedelta(seconds=5)

        mock_read.return_value = (
            [
                _make_entry(role="user", content="First command", timestamp=jsonl_ts),
                _make_entry(role="assistant", content="Working on it", timestamp=jsonl_ts),
            ],
            1000,
        )

        result = reconcile_agent_session(agent)

        assert len(result["created"]) == 2
        assert len(result["updated"]) == 0

        # Verify turns were created
        for turn_id in result["created"]:
            turn = db.session.get(Turn, turn_id)
            assert turn is not None
            assert turn.task_id == task.id
            assert turn.timestamp_source == "jsonl"

    @patch("claude_headspace.services.transcript_reader.read_new_entries_from_position")
    def test_reconcile_agent_session_skips_existing_turns(self, mock_read, app_ctx, agent, task):
        """Turns that already exist in the DB should be skipped."""
        agent.transcript_path = "/tmp/test-transcript.jsonl"
        now = datetime.now(timezone.utc)

        # Create existing turn
        existing = Turn(
            task_id=task.id,
            actor=TurnActor.USER,
            intent=TurnIntent.COMMAND,
            text="Already recorded",
            timestamp=now,
        )
        db.session.add(existing)
        db.session.flush()

        mock_read.return_value = (
            [
                _make_entry(role="user", content="Already recorded", timestamp=now),
                _make_entry(role="user", content="New command", timestamp=now),
            ],
            1000,
        )

        result = reconcile_agent_session(agent)

        assert len(result["created"]) == 1
        new_turn = db.session.get(Turn, result["created"][0])
        assert new_turn.text == "New command"

    @patch("claude_headspace.services.transcript_reader.read_new_entries_from_position")
    def test_reconcile_agent_session_empty_entries(self, mock_read, app_ctx, agent, task):
        """Empty entries list returns empty result."""
        agent.transcript_path = "/tmp/test-transcript.jsonl"
        mock_read.return_value = ([], 0)

        result = reconcile_agent_session(agent)
        assert result == {"updated": [], "created": []}
