"""ActivityMetric model for time-series activity metrics storage."""

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer
from sqlalchemy.orm import Mapped, mapped_column

from ..database import db


class ActivityMetric(db.Model):
    """
    Stores computed activity metrics at hourly bucket granularity.

    Each record is scoped to exactly one of: a specific agent, a specific
    project, or overall (system-wide). Metrics include turn count and
    average turn time, with optional active agent counts for project/overall.
    """

    __tablename__ = "activity_metrics"

    id: Mapped[int] = mapped_column(primary_key=True)
    bucket_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
    )

    # Scope — exactly one of these set
    agent_id: Mapped[int | None] = mapped_column(
        ForeignKey("agents.id", ondelete="CASCADE"), nullable=True,
    )
    project_id: Mapped[int | None] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=True,
    )
    is_overall: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False,
    )

    # Metrics
    turn_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    avg_turn_time_seconds: Mapped[float | None] = mapped_column(
        Float, nullable=True,
    )
    active_agents: Mapped[int | None] = mapped_column(
        Integer, nullable=True,
    )
    total_frustration: Mapped[int | None] = mapped_column(
        Integer, nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        scope = "overall" if self.is_overall else f"agent={self.agent_id}" if self.agent_id else f"project={self.project_id}"
        return f"<ActivityMetric id={self.id} bucket={self.bucket_start} {scope} turns={self.turn_count}>"


# Composite indexes for efficient time-range queries
Index("ix_activity_metrics_agent_bucket", ActivityMetric.agent_id, ActivityMetric.bucket_start)
Index("ix_activity_metrics_project_bucket", ActivityMetric.project_id, ActivityMetric.bucket_start)
Index("ix_activity_metrics_overall_bucket", ActivityMetric.is_overall, ActivityMetric.bucket_start)
