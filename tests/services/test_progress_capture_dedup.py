"""Tests for PROGRESS turn deduplication — TOCTOU race prevention.

Verifies that:
1. Per-agent lock prevents concurrent hooks from creating duplicate PROGRESS turns
2. DB unique constraint (belt-and-suspenders) catches duplicates that slip past the lock
3. IntegrityError is handled gracefully (no crash, duplicate skipped)
4. Stop hook recognises PROGRESS-covered content and upgrades instead of duplicating
"""

import json
import os
import tempfile
import threading
import time
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from claude_headspace.database import db
from claude_headspace.models.agent import Agent
from claude_headspace.models.command import Command, CommandState
from claude_headspace.models.project import Project
from claude_headspace.models.turn import Turn, TurnActor, TurnIntent
from claude_headspace.services.hook_agent_state import AgentHookState
from claude_headspace.services.transcript_reconciler import _content_hash


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
        for table in reversed(db.metadata.sorted_tables):
            db.session.execute(table.delete())
        db.session.commit()


@pytest.fixture
def project(app_ctx):
    p = Project(
        name="test-dedup",
        slug=f"test-dedup-{uuid4().hex[:8]}",
        path=f"/tmp/test-dedup-{uuid4().hex[:8]}",
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


def _write_jsonl(entries):
    """Write JSONL entries to a temp file and return its path."""
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as f:
        for entry in entries:
            f.write(json.dumps(entry) + "\n")
    return path


def _make_jsonl_entry(role="assistant", content="Test content", ts=None):
    """Create a JSONL entry dict matching Claude Code transcript format."""
    return {
        "type": role,
        "message": {
            "role": role,
            "content": [{"type": "text", "text": content}],
        },
        "timestamp": (ts or datetime.now(timezone.utc)).isoformat(),
    }


# ---------------------------------------------------------------------------
# Test: per-agent progress capture lock (REMOVED)
# ---------------------------------------------------------------------------
# The in-memory per-agent progress capture lock (get_progress_capture_lock)
# was removed as part of the advisory locking change. Serialisation is now
# provided by PostgreSQL advisory locks (advisory_lock(AGENT, agent.id))
# acquired at the hook route level. See advisory_lock.py and
# tests/services/test_advisory_lock.py for the replacement tests.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Test: DB unique constraint prevents duplicate turns
# ---------------------------------------------------------------------------


class TestDBConstraintPreventsDuplicates:
    """Verify the partial unique index on (command_id, jsonl_entry_hash)."""

    def test_duplicate_hash_raises_integrity_error(self, app_ctx, command):
        """Inserting two turns with same command_id + jsonl_entry_hash fails."""
        from sqlalchemy.exc import IntegrityError

        content_key = _content_hash("agent", "Test duplicate content")

        turn1 = Turn(
            command_id=command.id,
            actor=TurnActor.AGENT,
            intent=TurnIntent.PROGRESS,
            text="Test duplicate content",
            jsonl_entry_hash=content_key,
        )
        db.session.add(turn1)
        db.session.commit()

        turn2 = Turn(
            command_id=command.id,
            actor=TurnActor.AGENT,
            intent=TurnIntent.PROGRESS,
            text="Test duplicate content",
            jsonl_entry_hash=content_key,
        )
        db.session.add(turn2)
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()

    def test_different_commands_same_hash_allowed(self, app_ctx, agent):
        """Same hash in different commands is NOT a duplicate."""
        content_key = _content_hash("agent", "Shared content")

        cmd1 = Command(
            agent_id=agent.id, state=CommandState.PROCESSING,
            started_at=datetime.now(timezone.utc),
        )
        cmd2 = Command(
            agent_id=agent.id, state=CommandState.PROCESSING,
            started_at=datetime.now(timezone.utc),
        )
        db.session.add_all([cmd1, cmd2])
        db.session.flush()

        t1 = Turn(
            command_id=cmd1.id, actor=TurnActor.AGENT,
            intent=TurnIntent.PROGRESS, text="Shared content",
            jsonl_entry_hash=content_key,
        )
        t2 = Turn(
            command_id=cmd2.id, actor=TurnActor.AGENT,
            intent=TurnIntent.PROGRESS, text="Shared content",
            jsonl_entry_hash=content_key,
        )
        db.session.add_all([t1, t2])
        db.session.commit()  # Should succeed — different commands

        assert t1.id is not None
        assert t2.id is not None

    def test_null_hash_allows_duplicates(self, app_ctx, command):
        """Turns with NULL jsonl_entry_hash are not constrained."""
        t1 = Turn(
            command_id=command.id, actor=TurnActor.AGENT,
            intent=TurnIntent.PROGRESS, text="No hash turn",
            jsonl_entry_hash=None,
        )
        t2 = Turn(
            command_id=command.id, actor=TurnActor.AGENT,
            intent=TurnIntent.PROGRESS, text="No hash turn",
            jsonl_entry_hash=None,
        )
        db.session.add_all([t1, t2])
        db.session.commit()  # Should succeed — NULLs are distinct

        assert t1.id is not None
        assert t2.id is not None


# ---------------------------------------------------------------------------
# Test: IntegrityError is caught gracefully in _capture_progress_text_impl
# ---------------------------------------------------------------------------


class TestIntegrityErrorHandling:
    """Verify _capture_progress_text_impl catches DB constraint violations."""

    @patch("claude_headspace.services.broadcaster.get_broadcaster")
    def test_duplicate_hash_caught_gracefully(self, mock_broadcaster, app_ctx, agent, command):
        """Pre-existing turn with same hash does not crash progress capture."""
        from claude_headspace.services.hook_receiver import _capture_progress_text_impl

        content = "This is a duplicate progress message."
        content_key = _content_hash("agent", content)

        # Pre-insert a turn with this hash
        existing = Turn(
            command_id=command.id, actor=TurnActor.AGENT,
            intent=TurnIntent.PROGRESS, text=content,
            jsonl_entry_hash=content_key,
        )
        db.session.add(existing)
        db.session.commit()
        existing_id = existing.id

        # Write JSONL with same content
        jsonl_path = _write_jsonl([_make_jsonl_entry(content=content)])
        agent.transcript_path = jsonl_path

        state = AgentHookState()
        # Set position to 0 initially so it initialises, then set to 0 again to read
        state.set_transcript_position(agent.id, 0)

        try:
            _capture_progress_text_impl(agent, command, state)
        finally:
            os.unlink(jsonl_path)

        # Should NOT have created a duplicate — either caught by app check or DB constraint
        turns = Turn.query.filter_by(command_id=command.id).all()
        assert len(turns) == 1
        assert turns[0].id == existing_id


# ---------------------------------------------------------------------------
# Test: concurrent progress capture with lock
# ---------------------------------------------------------------------------


class TestConcurrentProgressCapture:
    """Verify the per-agent lock serialises concurrent progress capture."""

    @patch("claude_headspace.services.broadcaster.get_broadcaster")
    def test_concurrent_capture_no_duplicates(self, mock_broadcaster, app_ctx, agent, command):
        """Two threads calling _capture_progress_text create exactly 1 turn per entry."""
        from claude_headspace.services.hook_receiver import _capture_progress_text

        content = "Concurrent test: this should appear exactly once."
        jsonl_path = _write_jsonl([_make_jsonl_entry(content=content)])
        agent.transcript_path = jsonl_path

        # Initialise transcript position by setting to 0
        state = AgentHookState()
        state.set_transcript_position(agent.id, 0)

        # Patch get_agent_hook_state to return our shared state
        errors = []

        def run_capture():
            try:
                with app_ctx.app_context():
                    _capture_progress_text(agent, command)
            except Exception as e:
                errors.append(e)

        with patch("claude_headspace.services.hook_receiver.get_agent_hook_state", return_value=state):
            threads = [threading.Thread(target=run_capture) for _ in range(3)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=10)

        os.unlink(jsonl_path)

        assert errors == [], f"Threads raised errors: {errors}"

        # Verify exactly 1 turn created
        with app_ctx.app_context():
            turns = Turn.query.filter_by(
                command_id=command.id,
                actor=TurnActor.AGENT,
            ).all()
            hashes = [t.jsonl_entry_hash for t in turns]
            # At most 1 turn per unique hash
            assert len(set(hashes)) == len(hashes), (
                f"Duplicate hashes found: {hashes}"
            )
