"""Message model and MessageType enum."""

import enum
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import db

if TYPE_CHECKING:
    from .agent import Agent
    from .channel import Channel
    from .command import Command
    from .persona import Persona
    from .turn import Turn


class MessageType(enum.Enum):
    """Structural type of a channel message."""

    MESSAGE = "message"
    SYSTEM = "system"
    DELEGATION = "delegation"
    ESCALATION = "escalation"


class Message(db.Model):
    """
    Represents an immutable message in a channel.

    Messages are write-once records — no edit/delete lifecycle columns.
    Provides bidirectional traceability to the existing Turn and Command
    models via source_turn_id and source_command_id FKs.
    """

    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    channel_id: Mapped[int] = mapped_column(
        ForeignKey("channels.id", ondelete="CASCADE"), nullable=False, index=True
    )
    persona_id: Mapped[int | None] = mapped_column(
        ForeignKey("personas.id", ondelete="SET NULL"), nullable=True, index=True
    )
    agent_id: Mapped[int | None] = mapped_column(
        ForeignKey("agents.id", ondelete="SET NULL"), nullable=True, index=True
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    message_type: Mapped[MessageType] = mapped_column(
        Enum(MessageType, name="messagetype", create_constraint=True), nullable=False
    )
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)
    attachment_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    source_turn_id: Mapped[int | None] = mapped_column(
        ForeignKey("turns.id", ondelete="SET NULL"), nullable=True
    )
    source_command_id: Mapped[int | None] = mapped_column(
        ForeignKey("commands.id", ondelete="SET NULL"), nullable=True
    )
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    channel: Mapped["Channel"] = relationship("Channel", back_populates="messages")
    persona: Mapped["Persona | None"] = relationship("Persona")
    agent: Mapped["Agent | None"] = relationship("Agent")
    source_turn: Mapped["Turn | None"] = relationship(
        "Turn", foreign_keys=[source_turn_id]
    )
    source_command: Mapped["Command | None"] = relationship("Command")

    def __repr__(self) -> str:
        return (
            f"<Message id={self.id} channel_id={self.channel_id} "
            f"type={self.message_type.value}>"
        )
