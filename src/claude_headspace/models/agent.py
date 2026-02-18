"""Agent model."""

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import db
from .command import CommandState

if TYPE_CHECKING:
    from .project import Project
    from .command import Command


class Agent(db.Model):
    """
    Represents a Claude Code session.

    Agents belong to a Project and have multiple Commands. The agent's state
    is derived from its current (most recent incomplete) command.
    """

    __tablename__ = "agents"
    __table_args__ = (
        CheckConstraint(
            "(priority_score IS NULL AND priority_reason IS NULL AND priority_updated_at IS NULL) OR "
            "(priority_score IS NOT NULL AND priority_reason IS NOT NULL AND priority_updated_at IS NOT NULL)",
            name='ck_agents_priority_consistency',
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    session_uuid: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False, unique=True, index=True
    )
    claude_session_id: Mapped[str | None] = mapped_column(
        nullable=True, index=True,
    )
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    iterm_pane_id: Mapped[str | None] = mapped_column(nullable=True)
    tmux_pane_id: Mapped[str | None] = mapped_column(nullable=True)
    tmux_session: Mapped[str | None] = mapped_column(
        String(128), nullable=True, default=None
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )

    # Transcript path for content capture
    transcript_path: Mapped[str | None] = mapped_column(
        String(1024), nullable=True, default=None
    )

    # Priority scoring fields
    priority_score: Mapped[int | None] = mapped_column(
        Integer, nullable=True, default=None
    )
    priority_reason: Mapped[str | None] = mapped_column(
        Text, nullable=True, default=None
    )
    priority_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )

    # Context monitoring fields
    context_percent_used: Mapped[int | None] = mapped_column(
        Integer, nullable=True, default=None
    )
    context_remaining_tokens: Mapped[str | None] = mapped_column(
        String(32), nullable=True, default=None
    )
    context_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="agents")
    commands: Mapped[list["Command"]] = relationship(
        "Command",
        back_populates="agent",
        cascade="all, delete-orphan",
        order_by="Command.started_at.desc()",
    )

    @property
    def state(self) -> CommandState:
        """
        Derive agent state from current command.

        Returns:
            The current command's state, or IDLE if no active command
        """
        current_command = self.get_current_command()
        if current_command is None:
            return CommandState.IDLE
        return current_command.state

    @property
    def name(self) -> str:
        """
        Get a human-readable name for the agent.

        Returns:
            Name derived from session UUID prefix and project name
        """
        session_prefix = str(self.session_uuid)[:8]
        if self.project:
            return f"{self.project.name}/{session_prefix}"
        return f"Agent-{session_prefix}"

    def get_current_command(self) -> "Command | None":
        """
        Get the most recent incomplete command for this agent.

        Returns:
            The most recent Command with state != COMPLETE, or None
        """
        from .command import Command

        return (
            db.session.query(Command)
            .filter(Command.agent_id == self.id, Command.state != CommandState.COMPLETE)
            .order_by(Command.started_at.desc())
            .first()
        )

    def __repr__(self) -> str:
        return f"<Agent id={self.id} session_uuid={self.session_uuid}>"


# Additional indexes
Index("ix_agents_project_id_last_seen_at", Agent.project_id, Agent.last_seen_at)
