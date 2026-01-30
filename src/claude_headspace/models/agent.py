"""Agent model."""

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import db
from .task import TaskState

if TYPE_CHECKING:
    from .project import Project
    from .task import Task


class Agent(db.Model):
    """
    Represents a Claude Code session.

    Agents belong to a Project and have multiple Tasks. The agent's state
    is derived from its current (most recent incomplete) task.
    """

    __tablename__ = "agents"

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
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="agents")
    tasks: Mapped[list["Task"]] = relationship(
        "Task",
        back_populates="agent",
        cascade="all, delete-orphan",
        order_by="Task.started_at.desc()",
    )

    @property
    def state(self) -> TaskState:
        """
        Derive agent state from current task.

        Returns:
            The current task's state, or IDLE if no active task
        """
        current_task = self.get_current_task()
        if current_task is None:
            return TaskState.IDLE
        return current_task.state

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

    def get_current_task(self) -> "Task | None":
        """
        Get the most recent incomplete task for this agent.

        Returns:
            The most recent Task with state != COMPLETE, or None
        """
        from .task import Task

        return (
            db.session.query(Task)
            .filter(Task.agent_id == self.id, Task.state != TaskState.COMPLETE)
            .order_by(Task.started_at.desc())
            .first()
        )

    def __repr__(self) -> str:
        return f"<Agent id={self.id} session_uuid={self.session_uuid}>"


# Additional indexes
Index("ix_agents_project_id_last_seen_at", Agent.project_id, Agent.last_seen_at)
