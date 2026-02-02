"""Staleness detection service for classifying project freshness."""

import logging
from datetime import datetime, timezone
from enum import Enum

from ..config import get_value

logger = logging.getLogger(__name__)


class FreshnessTier(str, Enum):
    """Project freshness classification."""

    FRESH = "fresh"
    AGING = "aging"
    STALE = "stale"
    UNKNOWN = "unknown"


class StalenessService:
    """
    Classifies projects into freshness tiers based on agent activity.

    Uses Agent.last_seen_at timestamps to determine how recently
    a project has been actively worked on.
    """

    def __init__(self, app=None):
        """
        Initialize the staleness service.

        Args:
            app: Flask application instance for config access
        """
        self._app = app
        config = app.config.get("APP_CONFIG", {}) if app else {}
        self._stale_days = get_value(
            config, "brain_reboot", "staleness_threshold_days", default=7
        )
        self._aging_days = get_value(
            config, "brain_reboot", "aging_threshold_days", default=4
        )

    def get_last_activity(self, project) -> datetime | None:
        """
        Get the most recent agent activity timestamp for a project.

        Args:
            project: Project model instance with agents relationship

        Returns:
            Most recent last_seen_at datetime, or None if no agents
        """
        if not project.agents:
            return None

        last_seen = None
        for agent in project.agents:
            if agent.last_seen_at is not None:
                if last_seen is None or agent.last_seen_at > last_seen:
                    last_seen = agent.last_seen_at

        return last_seen

    def classify_project(self, project) -> dict:
        """
        Classify a single project's freshness tier.

        Args:
            project: Project model instance with agents relationship

        Returns:
            Dict with tier, days_since_activity, last_activity
        """
        last_activity = self.get_last_activity(project)

        if last_activity is None:
            return {
                "tier": FreshnessTier.UNKNOWN,
                "days_since_activity": None,
                "last_activity": None,
            }

        now = datetime.now(timezone.utc)
        delta = now - last_activity
        days = delta.total_seconds() / 86400  # Convert to fractional days

        if days >= self._stale_days:
            tier = FreshnessTier.STALE
        elif days >= self._aging_days:
            tier = FreshnessTier.AGING
        else:
            tier = FreshnessTier.FRESH

        return {
            "tier": tier,
            "days_since_activity": round(days, 1),
            "last_activity": last_activity,
        }

    def classify_projects(self, projects) -> dict:
        """
        Batch classify multiple projects.

        Args:
            projects: List of Project model instances

        Returns:
            Dict mapping project_id to classification result
        """
        results = {}
        for project in projects:
            results[project.id] = self.classify_project(project)
        return results
