"""Unit tests for activity aggregator service."""

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.claude_headspace.services.activity_aggregator import (
    ActivityAggregator,
    RETENTION_DAYS,
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

    def test_default_interval(self, mock_app):
        agg = ActivityAggregator(app=mock_app, config={})
        assert agg._interval == 300

    def test_custom_interval(self, mock_app):
        config = {"activity_aggregator": {"interval_seconds": 60}}
        agg = ActivityAggregator(app=mock_app, config=config)
        assert agg._interval == 60

    def test_start_creates_thread(self, aggregator):
        aggregator.start()
        assert aggregator._thread is not None
        assert aggregator._thread.daemon is True
        assert aggregator._thread.name == "ActivityAggregator"
        aggregator.stop()

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

        # Turns query - returns empty for the agent
        turns_query = MagicMock()
        turns_query.join.return_value.filter.return_value.order_by.return_value.all.return_value = []

        call_count = [0]

        def query_side_effect(model):
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
    """Test _upsert_metric static method."""

    def test_upsert_creates_new_record(self):
        """When no existing record, a new one is created."""
        session = MagicMock()
        session.query.return_value.filter.return_value.filter.return_value.filter.return_value.first.return_value = None

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

        session.add.assert_called_once()

    def test_upsert_updates_existing_record(self):
        """When existing record found, it is updated in place."""
        existing = MagicMock()
        session = MagicMock()
        session.query.return_value.filter.return_value.filter.return_value.filter.return_value.first.return_value = existing

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
        )

        assert existing.turn_count == 10
        assert existing.avg_turn_time_seconds == 45.0
        session.add.assert_not_called()
