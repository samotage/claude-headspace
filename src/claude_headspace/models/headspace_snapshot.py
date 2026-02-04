"""HeadspaceSnapshot model for persisting headspace state over time."""

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ..database import db


class HeadspaceSnapshot(db.Model):
    """Snapshot of headspace state at a point in time.

    Created after each headspace recalculation (per user turn with frustration score).
    Records rolling averages, traffic light state, flow state, and alert tracking.
    """

    __tablename__ = "headspace_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    frustration_rolling_10: Mapped[float | None] = mapped_column(Float, nullable=True)
    frustration_rolling_30min: Mapped[float | None] = mapped_column(Float, nullable=True)
    frustration_rolling_3hr: Mapped[float | None] = mapped_column(Float, nullable=True)
    state: Mapped[str] = mapped_column(String(10), nullable=False, default="green")
    turn_rate_per_hour: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_flow_state: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    flow_duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_alert_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    alert_count_today: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return f"<HeadspaceSnapshot id={self.id} state={self.state} ts={self.timestamp}>"


Index("ix_headspace_snapshots_timestamp", HeadspaceSnapshot.timestamp)
