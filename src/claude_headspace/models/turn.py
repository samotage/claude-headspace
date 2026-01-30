"""Turn model with TurnActor and TurnIntent enums."""

import enum
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import db


class TurnActor(enum.Enum):
    """Who produced the turn: user or agent."""

    USER = "user"
    AGENT = "agent"


class TurnIntent(enum.Enum):
    """The intent/type of the turn."""

    COMMAND = "command"
    ANSWER = "answer"
    QUESTION = "question"
    COMPLETION = "completion"
    PROGRESS = "progress"


class Turn(db.Model):
    """
    Represents an individual exchange in a Task.

    Each turn captures who said what (actor), why (intent), and when.
    """

    __tablename__ = "turns"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    actor: Mapped[TurnActor] = mapped_column(
        Enum(TurnActor, name="turnactor", create_constraint=True), nullable=False
    )
    intent: Mapped[TurnIntent] = mapped_column(
        Enum(TurnIntent, name="turnintent", create_constraint=True), nullable=False
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), index=True
    )

    # Relationships
    task: Mapped["Task"] = relationship("Task", back_populates="turns")

    def __repr__(self) -> str:
        return f"<Turn id={self.id} actor={self.actor.value} intent={self.intent.value}>"


# Additional indexes
Index("ix_turns_task_id_timestamp", Turn.task_id, Turn.timestamp)
