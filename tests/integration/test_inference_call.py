"""Integration tests for InferenceCall model persistence."""

from datetime import datetime, timezone

import pytest

from claude_headspace.models.inference_call import InferenceCall, InferenceLevel


@pytest.fixture(autouse=True)
def _set_factory_session(db_session):
    """Make db_session available for direct use."""
    pass


class TestInferenceCallPersistence:
    """Test InferenceCall model persists correctly in PostgreSQL."""

    def test_create_successful_call(self, db_session):
        """Test creating a successful inference call record."""
        call = InferenceCall(
            timestamp=datetime.now(timezone.utc),
            level=InferenceLevel.TURN.value,
            purpose="Turn summarisation",
            model="anthropic/claude-3-haiku",
            input_tokens=150,
            output_tokens=50,
            input_hash="abc123def456" * 4 + "abcdef1234567890",
            result_text="This turn covers...",
            latency_ms=320,
            cost=0.0004,
            cached=False,
        )
        db_session.add(call)
        db_session.commit()

        fetched = db_session.query(InferenceCall).filter_by(id=call.id).one()
        assert fetched.level == "turn"
        assert fetched.purpose == "Turn summarisation"
        assert fetched.model == "anthropic/claude-3-haiku"
        assert fetched.input_tokens == 150
        assert fetched.output_tokens == 50
        assert fetched.result_text == "This turn covers..."
        assert fetched.latency_ms == 320
        assert fetched.cached is False

    def test_create_failed_call(self, db_session):
        """Test creating a failed inference call with error message."""
        call = InferenceCall(
            timestamp=datetime.now(timezone.utc),
            level=InferenceLevel.PROJECT.value,
            purpose="Project analysis",
            model="anthropic/claude-3.5-sonnet",
            input_hash="aaa111bbb222" * 4 + "abcdef1234567890",
            error_message="API error 429: Rate limited",
            cached=False,
        )
        db_session.add(call)
        db_session.commit()

        fetched = db_session.query(InferenceCall).filter_by(id=call.id).one()
        assert fetched.result_text is None
        assert fetched.input_tokens is None
        assert fetched.error_message == "API error 429: Rate limited"

    def test_create_cached_call(self, db_session):
        """Test creating a cached inference call."""
        call = InferenceCall(
            timestamp=datetime.now(timezone.utc),
            level=InferenceLevel.COMMAND.value,
            purpose="Command summarisation",
            model="anthropic/claude-3-haiku",
            input_tokens=100,
            output_tokens=40,
            input_hash="cache111222" * 4 + "abcdef12345678901234",
            result_text="Cached result text",
            latency_ms=0,
            cost=0.0,
            cached=True,
        )
        db_session.add(call)
        db_session.commit()

        fetched = db_session.query(InferenceCall).filter_by(id=call.id).one()
        assert fetched.cached is True
        assert fetched.latency_ms == 0

    def test_all_inference_levels(self, db_session):
        """Test all InferenceLevel enum values persist correctly."""
        for level in InferenceLevel:
            call = InferenceCall(
                timestamp=datetime.now(timezone.utc),
                level=level.value,
                purpose=f"Test {level.value}",
                model="anthropic/claude-3-haiku",
                cached=False,
            )
            db_session.add(call)
        db_session.commit()

        count = db_session.query(InferenceCall).count()
        assert count == 4

    def test_optional_fk_associations(self, db_session):
        """Test that optional FK fields can be null."""
        call = InferenceCall(
            timestamp=datetime.now(timezone.utc),
            level="turn",
            purpose="FK test",
            model="test-model",
            cached=False,
            project_id=None,
            agent_id=None,
            command_id=None,
            turn_id=None,
        )
        db_session.add(call)
        db_session.commit()

        fetched = db_session.query(InferenceCall).filter_by(id=call.id).one()
        assert fetched.project_id is None
        assert fetched.agent_id is None
        assert fetched.command_id is None
        assert fetched.turn_id is None

    def test_query_by_level(self, db_session):
        """Test querying calls by level."""
        for i in range(3):
            db_session.add(InferenceCall(
                timestamp=datetime.now(timezone.utc),
                level="turn",
                purpose=f"Turn call {i}",
                model="haiku",
                cached=False,
            ))
        for i in range(2):
            db_session.add(InferenceCall(
                timestamp=datetime.now(timezone.utc),
                level="project",
                purpose=f"Project call {i}",
                model="sonnet",
                cached=False,
            ))
        db_session.commit()

        turn_calls = db_session.query(InferenceCall).filter_by(level="turn").all()
        project_calls = db_session.query(InferenceCall).filter_by(level="project").all()
        assert len(turn_calls) == 3
        assert len(project_calls) == 2

    def test_query_by_input_hash(self, db_session):
        """Test querying by input_hash for cache lookups."""
        hash_value = "abcdef" * 10 + "abcd"
        call = InferenceCall(
            timestamp=datetime.now(timezone.utc),
            level="turn",
            purpose="Hash test",
            model="haiku",
            input_hash=hash_value,
            cached=False,
        )
        db_session.add(call)
        db_session.commit()

        found = db_session.query(InferenceCall).filter_by(input_hash=hash_value).first()
        assert found is not None
        assert found.purpose == "Hash test"

    def test_repr(self, db_session):
        """Test model __repr__."""
        call = InferenceCall(
            timestamp=datetime.now(timezone.utc),
            level="turn",
            purpose="Repr test",
            model="haiku",
            cached=False,
        )
        db_session.add(call)
        db_session.commit()

        assert "InferenceCall" in repr(call)
        assert "turn" in repr(call)
        assert "haiku" in repr(call)
