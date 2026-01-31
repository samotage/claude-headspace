"""InferenceCall model for logging LLM inference calls."""

import enum
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..database import db


class InferenceLevel(str, enum.Enum):
    """Inference level determines model selection."""

    TURN = "turn"
    TASK = "task"
    PROJECT = "project"
    OBJECTIVE = "objective"


class InferenceCall(db.Model):
    """
    Records every LLM inference call for auditing and cost tracking.

    Each call logs the model used, token counts, latency, cost,
    and optional associations to domain entities.
    """

    __tablename__ = "inference_calls"

    id: Mapped[int] = mapped_column(primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), index=True
    )
    level: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    purpose: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    input_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    result_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    cached: Mapped[bool] = mapped_column(nullable=False, default=False)

    # Optional FK associations to domain entities
    project_id: Mapped[int | None] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True
    )
    agent_id: Mapped[int | None] = mapped_column(
        ForeignKey("agents.id", ondelete="SET NULL"), nullable=True
    )
    task_id: Mapped[int | None] = mapped_column(
        ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True
    )
    turn_id: Mapped[int | None] = mapped_column(
        ForeignKey("turns.id", ondelete="SET NULL"), nullable=True
    )

    def __repr__(self) -> str:
        return f"<InferenceCall id={self.id} level={self.level} model={self.model}>"


# Composite indexes for common query patterns
Index("ix_inference_calls_level_timestamp", InferenceCall.level, InferenceCall.timestamp)
Index("ix_inference_calls_model_timestamp", InferenceCall.model, InferenceCall.timestamp)
