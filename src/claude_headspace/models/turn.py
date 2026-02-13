"""Turn model with TurnActor and TurnIntent enums."""

import enum
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
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
    END_OF_TASK = "end_of_task"


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
    # Temporal validation (turn.timestamp >= task.started_at) is enforced at
    # application level — cross-table CHECK constraints are not supported in PostgreSQL.
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), index=True
    )
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary_generated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    frustration_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tool_input: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    file_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Voice bridge: structured question detail
    question_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    question_options: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    question_source_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    answered_by_turn_id: Mapped[int | None] = mapped_column(
        ForeignKey("turns.id", ondelete="SET NULL"), nullable=True
    )

    # Relationships
    task: Mapped["Task"] = relationship("Task", back_populates="turns")
    answered_by: Mapped["Turn | None"] = relationship(
        "Turn", remote_side="Turn.id", foreign_keys=[answered_by_turn_id],
    )

    def __repr__(self) -> str:
        return f"<Turn id={self.id} actor={self.actor.value} intent={self.intent.value}>"


# Additional indexes
Index("ix_turns_task_id_timestamp", Turn.task_id, Turn.timestamp)
Index("ix_turns_task_id_actor", Turn.task_id, Turn.actor)
