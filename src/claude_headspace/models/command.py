"""Command model and CommandState enum."""

import enum
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import db


class CommandState(enum.Enum):
    """5-state lifecycle for commands."""

    IDLE = "idle"
    COMMANDED = "commanded"
    PROCESSING = "processing"
    AWAITING_INPUT = "awaiting_input"
    COMPLETE = "complete"


class Command(db.Model):
    """
    Represents a unit of work commanded to an agent.

    Commands have a 5-state lifecycle: idle → commanded → processing →
    awaiting_input → complete.
    """

    __tablename__ = "commands"

    id: Mapped[int] = mapped_column(primary_key=True)
    agent_id: Mapped[int] = mapped_column(
        ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    state: Mapped[CommandState] = mapped_column(
        Enum(CommandState, name="commandstate", create_constraint=True),
        nullable=False,
        default=CommandState.IDLE,
        index=True,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completion_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    completion_summary_generated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    instruction: Mapped[str | None] = mapped_column(Text, nullable=True)
    instruction_generated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    full_command: Mapped[str | None] = mapped_column(Text, nullable=True)
    full_output: Mapped[str | None] = mapped_column(Text, nullable=True)
    plan_file_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    plan_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    plan_approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    agent: Mapped["Agent"] = relationship("Agent", back_populates="commands")
    turns: Mapped[list["Turn"]] = relationship(
        "Turn",
        back_populates="command",
        cascade="all, delete-orphan",
        order_by="Turn.timestamp",
    )

    def get_recent_turns(self, limit: int = 10) -> list["Turn"]:
        """
        Get recent turns for this command, ordered by timestamp descending.

        Args:
            limit: Maximum number of turns to return

        Returns:
            List of Turn objects, most recent first
        """
        from .turn import Turn

        return (
            db.session.query(Turn)
            .filter(Turn.command_id == self.id)
            .order_by(Turn.timestamp.desc())
            .limit(limit)
            .all()
        )

    def __repr__(self) -> str:
        return f"<Command id={self.id} state={self.state.value} agent_id={self.agent_id}>"


# Additional indexes
Index("ix_commands_agent_id_state", Command.agent_id, Command.state)
