"""Objective and ObjectiveHistory models."""

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import db


class Objective(db.Model):
    """
    Represents the current global objective.

    The objective guides prioritisation across all projects.
    History of changes is tracked in ObjectiveHistory.
    """

    __tablename__ = "objectives"

    id: Mapped[int] = mapped_column(primary_key=True)
    current_text: Mapped[str] = mapped_column(Text, nullable=False)
    constraints: Mapped[str | None] = mapped_column(Text, nullable=True)
    priority_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    set_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    history: Mapped[list["ObjectiveHistory"]] = relationship(
        "ObjectiveHistory",
        back_populates="objective",
        cascade="all, delete-orphan",
        order_by="ObjectiveHistory.started_at.desc()",
    )

    def __repr__(self) -> str:
        return f"<Objective id={self.id} set_at={self.set_at}>"


class ObjectiveHistory(db.Model):
    """
    Tracks historical objective changes.

    Each record represents an objective that was active from started_at
    until ended_at (or still active if ended_at is None).
    """

    __tablename__ = "objective_histories"

    id: Mapped[int] = mapped_column(primary_key=True)
    objective_id: Mapped[int] = mapped_column(
        ForeignKey("objectives.id", ondelete="CASCADE"), nullable=False, index=True
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    constraints: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    objective: Mapped["Objective"] = relationship("Objective", back_populates="history")

    def __repr__(self) -> str:
        return f"<ObjectiveHistory id={self.id} objective_id={self.objective_id}>"
