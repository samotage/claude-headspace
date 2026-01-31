"""Tests for the staleness detection service."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from src.claude_headspace.services.staleness import (
    FreshnessTier,
    StalenessService,
)


@pytest.fixture
def mock_app():
    app = MagicMock()
    app.config = {
        "APP_CONFIG": {
            "brain_reboot": {
                "staleness_threshold_days": 7,
                "aging_threshold_days": 4,
            }
        }
    }
    return app


@pytest.fixture
def service(mock_app):
    return StalenessService(app=mock_app)


def _make_agent(last_seen_at):
    agent = MagicMock()
    agent.last_seen_at = last_seen_at
    return agent


def _make_project(agents=None):
    project = MagicMock()
    project.agents = agents or []
    project.id = 1
    return project


class TestGetLastActivity:
    def test_no_agents(self, service):
        project = _make_project(agents=[])
        assert service.get_last_activity(project) is None

    def test_single_agent(self, service):
        ts = datetime(2026, 1, 20, 12, 0, tzinfo=timezone.utc)
        project = _make_project(agents=[_make_agent(ts)])
        assert service.get_last_activity(project) == ts

    def test_multiple_agents_returns_most_recent(self, service):
        ts1 = datetime(2026, 1, 18, 12, 0, tzinfo=timezone.utc)
        ts2 = datetime(2026, 1, 20, 12, 0, tzinfo=timezone.utc)
        ts3 = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)
        project = _make_project(agents=[
            _make_agent(ts1), _make_agent(ts2), _make_agent(ts3)
        ])
        assert service.get_last_activity(project) == ts2

    def test_agent_with_none_last_seen(self, service):
        ts = datetime(2026, 1, 20, 12, 0, tzinfo=timezone.utc)
        agent_none = _make_agent(None)
        project = _make_project(agents=[agent_none, _make_agent(ts)])
        assert service.get_last_activity(project) == ts

    def test_all_agents_none_last_seen(self, service):
        project = _make_project(agents=[_make_agent(None), _make_agent(None)])
        assert service.get_last_activity(project) is None


class TestClassifyProject:
    def test_unknown_no_agents(self, service):
        project = _make_project(agents=[])
        result = service.classify_project(project)
        assert result["tier"] == FreshnessTier.UNKNOWN
        assert result["days_since_activity"] is None
        assert result["last_activity"] is None

    def test_fresh_recent_activity(self, service):
        now = datetime.now(timezone.utc)
        ts = now - timedelta(hours=6)
        project = _make_project(agents=[_make_agent(ts)])
        result = service.classify_project(project)
        assert result["tier"] == FreshnessTier.FRESH
        assert result["days_since_activity"] < 1

    def test_fresh_within_threshold(self, service):
        now = datetime.now(timezone.utc)
        ts = now - timedelta(days=2)
        project = _make_project(agents=[_make_agent(ts)])
        result = service.classify_project(project)
        assert result["tier"] == FreshnessTier.FRESH

    def test_aging_at_boundary(self, service):
        now = datetime.now(timezone.utc)
        ts = now - timedelta(days=4, hours=1)
        project = _make_project(agents=[_make_agent(ts)])
        result = service.classify_project(project)
        assert result["tier"] == FreshnessTier.AGING

    def test_aging_within_range(self, service):
        now = datetime.now(timezone.utc)
        ts = now - timedelta(days=5)
        project = _make_project(agents=[_make_agent(ts)])
        result = service.classify_project(project)
        assert result["tier"] == FreshnessTier.AGING

    def test_stale_at_boundary(self, service):
        now = datetime.now(timezone.utc)
        ts = now - timedelta(days=7, hours=1)
        project = _make_project(agents=[_make_agent(ts)])
        result = service.classify_project(project)
        assert result["tier"] == FreshnessTier.STALE

    def test_stale_very_old(self, service):
        now = datetime.now(timezone.utc)
        ts = now - timedelta(days=30)
        project = _make_project(agents=[_make_agent(ts)])
        result = service.classify_project(project)
        assert result["tier"] == FreshnessTier.STALE

    def test_days_since_activity_returned(self, service):
        now = datetime.now(timezone.utc)
        ts = now - timedelta(days=3)
        project = _make_project(agents=[_make_agent(ts)])
        result = service.classify_project(project)
        assert 2.9 <= result["days_since_activity"] <= 3.1

    def test_last_activity_returned(self, service):
        ts = datetime(2026, 1, 20, 12, 0, tzinfo=timezone.utc)
        project = _make_project(agents=[_make_agent(ts)])
        result = service.classify_project(project)
        assert result["last_activity"] == ts


class TestClassifyProjects:
    def test_empty_list(self, service):
        result = service.classify_projects([])
        assert result == {}

    def test_multiple_projects(self, service):
        now = datetime.now(timezone.utc)
        p1 = _make_project(agents=[_make_agent(now - timedelta(hours=1))])
        p1.id = 1
        p2 = _make_project(agents=[_make_agent(now - timedelta(days=5))])
        p2.id = 2
        p3 = _make_project(agents=[])
        p3.id = 3

        result = service.classify_projects([p1, p2, p3])
        assert result[1]["tier"] == FreshnessTier.FRESH
        assert result[2]["tier"] == FreshnessTier.AGING
        assert result[3]["tier"] == FreshnessTier.UNKNOWN


class TestConfigurableThresholds:
    def test_custom_thresholds(self):
        app = MagicMock()
        app.config = {
            "APP_CONFIG": {
                "brain_reboot": {
                    "staleness_threshold_days": 14,
                    "aging_threshold_days": 7,
                }
            }
        }
        svc = StalenessService(app=app)

        now = datetime.now(timezone.utc)
        # 5 days ago would be fresh with custom thresholds (< 7)
        ts = now - timedelta(days=5)
        project = _make_project(agents=[_make_agent(ts)])
        result = svc.classify_project(project)
        assert result["tier"] == FreshnessTier.FRESH

        # 10 days ago would be aging with custom thresholds (7-14)
        ts = now - timedelta(days=10)
        project = _make_project(agents=[_make_agent(ts)])
        result = svc.classify_project(project)
        assert result["tier"] == FreshnessTier.AGING

        # 15 days ago would be stale with custom thresholds (> 14)
        ts = now - timedelta(days=15)
        project = _make_project(agents=[_make_agent(ts)])
        result = svc.classify_project(project)
        assert result["tier"] == FreshnessTier.STALE

    def test_default_thresholds_no_app(self):
        svc = StalenessService(app=None)
        now = datetime.now(timezone.utc)
        ts = now - timedelta(days=5)
        project = _make_project(agents=[_make_agent(ts)])
        result = svc.classify_project(project)
        assert result["tier"] == FreshnessTier.AGING


class TestFreshnessTierEnum:
    def test_values(self):
        assert FreshnessTier.FRESH == "fresh"
        assert FreshnessTier.AGING == "aging"
        assert FreshnessTier.STALE == "stale"
        assert FreshnessTier.UNKNOWN == "unknown"

    def test_is_string(self):
        assert isinstance(FreshnessTier.FRESH, str)


class TestExactBoundary:
    def test_exactly_at_aging_boundary(self, service):
        """At exactly aging_threshold_days, should be aging."""
        now = datetime.now(timezone.utc)
        ts = now - timedelta(days=4)
        project = _make_project(agents=[_make_agent(ts)])
        result = service.classify_project(project)
        assert result["tier"] == FreshnessTier.AGING

    def test_just_below_aging_boundary(self, service):
        """Just under aging_threshold_days, should be fresh."""
        now = datetime.now(timezone.utc)
        ts = now - timedelta(days=3, hours=23)
        project = _make_project(agents=[_make_agent(ts)])
        result = service.classify_project(project)
        assert result["tier"] == FreshnessTier.FRESH

    def test_exactly_at_stale_boundary(self, service):
        """At exactly staleness_threshold_days, should be stale."""
        now = datetime.now(timezone.utc)
        ts = now - timedelta(days=7)
        project = _make_project(agents=[_make_agent(ts)])
        result = service.classify_project(project)
        assert result["tier"] == FreshnessTier.STALE

    def test_just_below_stale_boundary(self, service):
        """Just under staleness_threshold_days, should be aging."""
        now = datetime.now(timezone.utc)
        ts = now - timedelta(days=6, hours=23)
        project = _make_project(agents=[_make_agent(ts)])
        result = service.classify_project(project)
        assert result["tier"] == FreshnessTier.AGING
