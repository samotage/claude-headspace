"""Channel model and ChannelType enum."""

import enum
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, event
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import db
from ._slug import slugify, temp_slug

if TYPE_CHECKING:
    from .agent import Agent
    from .channel_membership import ChannelMembership
    from .message import Message
    from .organisation import Organisation
    from .persona import Persona
    from .project import Project


class ChannelType(enum.Enum):
    """Type of channel conversation."""

    WORKSHOP = "workshop"
    DELEGATION = "delegation"
    REVIEW = "review"
    STANDUP = "standup"
    BROADCAST = "broadcast"


class Channel(db.Model):
    """
    Represents a named conversation container for inter-agent communication.

    Channels exist at system level, cross-project by default, with optional
    Organisation and Project scoping via nullable FKs. The slug is auto-generated
    as {channel_type}-{name}-{id} after insert.
    """

    __tablename__ = "channels"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    slug: Mapped[str] = mapped_column(
        String(128), nullable=False, unique=True, default=temp_slug
    )
    channel_type: Mapped[ChannelType] = mapped_column(
        Enum(
            ChannelType,
            name="channeltype",
            create_constraint=True,
            values_callable=lambda e: [ct.value for ct in e],
        ),
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    intent_override: Mapped[str | None] = mapped_column(Text, nullable=True)
    organisation_id: Mapped[int | None] = mapped_column(
        ForeignKey("organisations.id", ondelete="SET NULL"), nullable=True
    )
    project_id: Mapped[int | None] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"), nullable=True
    )
    created_by_persona_id: Mapped[int | None] = mapped_column(
        ForeignKey("personas.id", ondelete="SET NULL"), nullable=True
    )
    spawned_from_agent_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("agents.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Scoping relationships (intentionally one-directional — no back_populates on targets)
    organisation: Mapped["Organisation | None"] = relationship("Organisation")
    project: Mapped["Project | None"] = relationship("Project")
    created_by_persona: Mapped["Persona | None"] = relationship("Persona")
    spawned_from_agent: Mapped["Agent | None"] = relationship(
        "Agent", foreign_keys=[spawned_from_agent_id]
    )

    # Children
    memberships: Mapped[list["ChannelMembership"]] = relationship(
        "ChannelMembership", back_populates="channel", cascade="all, delete-orphan"
    )
    messages: Mapped[list["Message"]] = relationship(
        "Message",
        back_populates="channel",
        cascade="all, delete-orphan",
        order_by="Message.sent_at",
    )

    def generate_slug(self) -> str:
        """Generate slug from channel type, name, and id.

        Format: {channel_type}-{name}-{id}, all lowercase, sanitized.
        """
        type_part = self.channel_type.value
        name_part = slugify(self.name)
        return f"{type_part}-{name_part}-{self.id}"

    def __repr__(self) -> str:
        return f"<Channel id={self.id} slug={self.slug} type={self.channel_type.value}>"


@event.listens_for(Channel, "after_insert")
def _set_channel_slug(mapper, connection, target):
    """Replace the temporary slug with the real one after insert provides the id."""
    slug = target.generate_slug()
    connection.execute(
        Channel.__table__.update()
        .where(Channel.__table__.c.id == target.id)
        .values(slug=slug)
    )
    target.slug = slug
