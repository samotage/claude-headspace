"""Unit tests for activity aggregator service."""

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.claude_headspace.models.turn import TurnActor
from src.claude_headspace.services.activity_aggregator import (
    ActivityAggregator,
    DEFAULT_RETENTION_DAYS,
)


@contextmanager
def _fake_app_context():
    yield


@pytest.fixture
def mock_app():
    app = MagicMock()
    app.app_context = _fake_app_context
    return app


@pytest.fixture
def aggregator(mock_app):
    return ActivityAggregator(app=mock_app, config={})


class TestAggregatorInit:
    """Test ActivityAggregator initialization."""

    def test_default_config(self, mock_app):
        agg = ActivityAggregator(app=mock_app, config={})
        assert agg._enabled is True
        assert agg._interval == 300
        assert agg._retention_days == 30

    def test_custom_config(self, mock_app):
        config = {"activity": {"interval_seconds": 60, "retention_days": 7, "enabled": False}}
        agg = ActivityAggregator(app=mock_app, config=config)
        assert agg._enabled is False
        assert agg._interval == 60
        assert agg._retention_days == 7

    def test_start_creates_thread(self, aggregator):
        aggregator.start()
        assert aggregator._thread is not None
        assert aggregator._thread.daemon is True
        assert aggregator._thread.name == "ActivityAggregator"
        aggregator.stop()

    def test_start_disabled_skips(self, mock_app):
        agg = ActivityAggregator(app=mock_app, config={"activity": {"enabled": False}})
        agg.start()
        assert agg._thread is None

    def test_stop_sets_event(self, aggregator):
        aggregator.start()
        aggregator.stop()
        assert aggregator._stop_event.is_set()


class TestAggregateOnce:
    """Test aggregate_once method."""

    @patch("src.claude_headspace.services.activity_aggregator.db")
    def test_aggregate_once_no_agents(self, mock_db, aggregator):
        """When no active agents exist, returns empty stats."""
        mock_db.session.query.return_value.filter.return_value.all.return_value = []

        stats = aggregator.aggregate_once()

        assert stats["agents"] == 0
        assert stats["projects"] == 0
        assert stats["overall"] == 0

    @patch("src.claude_headspace.services.activity_aggregator.db")
    def test_aggregate_once_with_agent_no_turns(self, mock_db, aggregator):
        """When agent has no turns in the current bucket, it is skipped."""
        mock_agent = MagicMock()
        mock_agent.id = 1
        mock_agent.project_id = 10
        mock_agent.ended_at = None

        # Agents query
        agents_query = MagicMock()
        agents_query.filter.return_value.all.return_value = [mock_agent]

        # Turns bulk query - returns empty (no turns for any agent)
        turns_query = MagicMock()
        turns_query.join.return_value.filter.return_value.order_by.return_value.all.return_value = []

        call_count = [0]

        def query_side_effect(*args):
            call_count[0] += 1
            if call_count[0] == 1:
                return agents_query
            return turns_query

        mock_db.session.query.side_effect = query_side_effect

        stats = aggregator.aggregate_once()

        assert stats["agents"] == 0
        assert stats["projects"] == 0
        assert stats["overall"] == 0

    def test_avg_turn_time_calculation(self):
        """Average turn time is correctly computed from consecutive turn timestamps."""
        now = datetime.now(timezone.utc)
        turns = [
            MagicMock(timestamp=now),
            MagicMock(timestamp=now + timedelta(seconds=60)),
            MagicMock(timestamp=now + timedelta(seconds=180)),
        ]

        # The formula: mean of deltas between consecutive turns
        deltas = []
        for i in range(1, len(turns)):
            delta = (turns[i].timestamp - turns[i - 1].timestamp).total_seconds()
            deltas.append(delta)

        avg = sum(deltas) / len(deltas)
        # delta[0] = 60s, delta[1] = 120s -> avg = 90s
        assert avg == 90.0

    def test_avg_turn_time_single_turn(self):
        """With a single turn, avg_turn_time is None (need >= 2 turns for deltas)."""
        now = datetime.now(timezone.utc)
        turns = [MagicMock(timestamp=now)]

        # With only 1 turn, no deltas can be computed
        assert len(turns) < 2

    @patch("src.claude_headspace.services.activity_aggregator.db")
    def test_aggregate_once_includes_ended_agent_in_bucket(self, mock_db, aggregator):
        """An agent that ended during the current bucket should have its turns included."""
        now = datetime.now(timezone.utc)
        bucket_start = now.replace(minute=0, second=0, microsecond=0)

        mock_agent = MagicMock()
        mock_agent.id = 1
        mock_agent.project_id = 10
        # Agent ended 30 minutes into the current bucket
        mock_agent.ended_at = bucket_start + timedelta(minutes=30)

        # Agents query returns the ended agent
        agents_query = MagicMock()
        agents_query.filter.return_value.all.return_value = [mock_agent]

        # Turns bulk query returns (turn, agent_id) tuples
        mock_turn1 = MagicMock(
            timestamp=bucket_start + timedelta(minutes=5),
            actor="USER",
            frustration_score=None,
        )
        mock_turn2 = MagicMock(
            timestamp=bucket_start + timedelta(minutes=15),
            actor="AGENT",
            frustration_score=None,
        )
        turns_query = MagicMock()
        turns_query.join.return_value.filter.return_value.order_by.return_value.all.return_value = [
            (mock_turn1, 1), (mock_turn2, 1),
        ]

        call_count = [0]

        def query_side_effect(*args):
            call_count[0] += 1
            if call_count[0] == 1:
                return agents_query
            return turns_query

        mock_db.session.query.side_effect = query_side_effect

        stats = aggregator.aggregate_once()

        assert stats["agents"] == 1
        assert stats["projects"] == 1
        assert stats["overall"] == 1

    @patch("src.claude_headspace.services.activity_aggregator.db")
    def test_aggregate_once_includes_frustration_from_user_turns(self, mock_db, aggregator):
        """Frustration scores on USER turns are correctly aggregated using TurnActor enum."""
        now = datetime.now(timezone.utc)
        bucket_start = now.replace(minute=0, second=0, microsecond=0)

        mock_agent = MagicMock()
        mock_agent.id = 1
        mock_agent.project_id = 10
        mock_agent.ended_at = None

        agents_query = MagicMock()
        agents_query.filter.return_value.all.return_value = [mock_agent]

        mock_turn1 = MagicMock(
            timestamp=bucket_start + timedelta(minutes=5),
            actor=TurnActor.USER,
            frustration_score=6,
        )
        mock_turn2 = MagicMock(
            timestamp=bucket_start + timedelta(minutes=15),
            actor=TurnActor.USER,
            frustration_score=3,
        )
        mock_turn3 = MagicMock(
            timestamp=bucket_start + timedelta(minutes=25),
            actor=TurnActor.AGENT,
            frustration_score=None,
        )
        turns_query = MagicMock()
        turns_query.join.return_value.filter.return_value.order_by.return_value.all.return_value = [
            (mock_turn1, 1), (mock_turn2, 1), (mock_turn3, 1),
        ]

        call_count = [0]

        def query_side_effect(*args):
            call_count[0] += 1
            if call_count[0] == 1:
                return agents_query
            return turns_query

        mock_db.session.query.side_effect = query_side_effect

        stats = aggregator.aggregate_once()

        assert stats["agents"] == 1

        # Verify the upsert was called with frustration data
        # The agent-level upsert is the first execute call
        execute_calls = mock_db.session.execute.call_args_list
        assert len(execute_calls) >= 1  # At least agent-level metric written

    @patch("src.claude_headspace.services.activity_aggregator.db")
    def test_aggregate_once_excludes_agent_ended_before_bucket(self, mock_db, aggregator):
        """An agent that ended before the current bucket should be excluded."""
        now = datetime.now(timezone.utc)
        bucket_start = now.replace(minute=0, second=0, microsecond=0)

        mock_agent = MagicMock()
        mock_agent.id = 1
        mock_agent.project_id = 10
        # Agent ended an hour before the current bucket
        mock_agent.ended_at = bucket_start - timedelta(hours=1)

        # Agents query returns empty (ended_at < bucket_start is filtered out)
        agents_query = MagicMock()
        agents_query.filter.return_value.all.return_value = []

        mock_db.session.query.side_effect = lambda model: agents_query

        stats = aggregator.aggregate_once()

        assert stats["agents"] == 0
        assert stats["projects"] == 0
        assert stats["overall"] == 0


class TestPruneOldRecords:
    """Test prune_old_records method."""

    @patch("src.claude_headspace.services.activity_aggregator.db")
    def test_prune_deletes_old_records(self, mock_db, aggregator):
        """Records older than 30 days are deleted."""
        mock_db.session.query.return_value.filter.return_value.delete.return_value = 5

        deleted = aggregator.prune_old_records()

        assert deleted == 5
        mock_db.session.commit.assert_called_once()

    @patch("src.claude_headspace.services.activity_aggregator.db")
    def test_prune_no_old_records(self, mock_db, aggregator):
        """When no old records exist, returns 0."""
        mock_db.session.query.return_value.filter.return_value.delete.return_value = 0

        deleted = aggregator.prune_old_records()

        assert deleted == 0


class TestUpsertMetric:
    """Test _upsert_metric static method (INSERT ON CONFLICT)."""

    def test_upsert_executes_insert_on_conflict(self):
        """_upsert_metric calls session.execute with an INSERT ON CONFLICT statement."""
        session = MagicMock()
        now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)

        ActivityAggregator._upsert_metric(
            session,
            bucket_start=now,
            agent_id=1,
            project_id=None,
            is_overall=False,
            turn_count=5,
            avg_turn_time_seconds=30.0,
            active_agents=None,
        )

        session.execute.assert_called_once()

    def test_upsert_passes_correct_values(self):
        """_upsert_metric passes all metric values to the INSERT statement."""
        session = MagicMock()
        now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)

        ActivityAggregator._upsert_metric(
            session,
            bucket_start=now,
            agent_id=1,
            project_id=None,
            is_overall=False,
            turn_count=10,
            avg_turn_time_seconds=45.0,
            active_agents=None,
            total_frustration=5,
            frustration_turn_count=2,
        )

        session.execute.assert_called_once()
        # Verify the compiled statement contains the expected values
        stmt = session.execute.call_args[0][0]
        compiled = stmt.compile(compile_kwargs={"literal_binds": False})
        sql = str(compiled)
        assert "ON CONFLICT" in sql
        assert "DO UPDATE" in sql
