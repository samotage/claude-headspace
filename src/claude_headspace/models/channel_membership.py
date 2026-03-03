"""ChannelMembership model."""

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import db

if TYPE_CHECKING:
    from .agent import Agent
    from .channel import Channel
    from .persona import Persona


class ChannelMembership(db.Model):
    """
    Represents a persona's membership in a channel.

    Links stable persona identities to channels with a mutable agent_id
    column to track which agent instance currently receives messages.
    The partial unique index uq_active_agent_one_channel (created in
    migration) prevents an agent from being active in multiple channels
    simultaneously.
    """

    __tablename__ = "channel_memberships"
    __table_args__ = (
        db.UniqueConstraint("channel_id", "persona_id", name="uq_channel_persona"),
        Index(
            "uq_active_agent_one_channel",
            "agent_id",
            unique=True,
            postgresql_where=text("status = 'active' AND agent_id IS NOT NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    channel_id: Mapped[int] = mapped_column(
        ForeignKey("channels.id", ondelete="CASCADE"), nullable=False, index=True
    )
    persona_id: Mapped[int] = mapped_column(
        ForeignKey("personas.id", ondelete="CASCADE"), nullable=False, index=True
    )
    agent_id: Mapped[int | None] = mapped_column(
        ForeignKey("agents.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # FK to position_assignments deferred — table does not yet exist.
    # Will be added as a FK constraint when PositionAssignment model is implemented.
    position_assignment_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    is_chair: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="active"
    )
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    left_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    channel: Mapped["Channel"] = relationship("Channel", back_populates="memberships")
    persona: Mapped["Persona"] = relationship("Persona")
    agent: Mapped["Agent | None"] = relationship("Agent")

    def __repr__(self) -> str:
        return (
            f"<ChannelMembership id={self.id} "
            f"channel_id={self.channel_id} persona_id={self.persona_id} "
            f"status={self.status}>"
        )
