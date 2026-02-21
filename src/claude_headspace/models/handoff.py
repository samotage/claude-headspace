"""Handoff model."""

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import db

if TYPE_CHECKING:
    from .agent import Agent


class Handoff(db.Model):
    """
    Represents a handoff record for agent context handoff.

    Each Handoff belongs to an outgoing agent (the one that produced the handoff)
    and captures the orchestration metadata: reason, file path to the handoff
    document, and the injection prompt sent to the successor agent.
    """

    __tablename__ = "handoffs"

    id: Mapped[int] = mapped_column(primary_key=True)
    agent_id: Mapped[int] = mapped_column(
        ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    reason: Mapped[str] = mapped_column(String(64), nullable=False)
    file_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    injection_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    agent: Mapped["Agent"] = relationship("Agent", back_populates="handoff")

    def __repr__(self) -> str:
        return f"<Handoff id={self.id} agent_id={self.agent_id} reason={self.reason}>"
