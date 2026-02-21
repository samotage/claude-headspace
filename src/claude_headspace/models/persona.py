"""Persona model."""

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text, event
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import db

if TYPE_CHECKING:
    from .agent import Agent
    from .role import Role


def _temp_slug() -> str:
    """Generate a temporary slug for initial insert (replaced by after_insert event)."""
    return f"_pending_{uuid4().hex[:12]}"


class Persona(db.Model):
    """
    Represents a named agent identity (e.g., Con, Robbo, Verner).

    Each Persona references exactly one Role via a foreign key. The slug
    is auto-generated as {role_name}-{persona_name}-{id} after insert and
    serves as the filesystem path key for persona assets.
    """

    __tablename__ = "personas"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(
        String(128), nullable=False, unique=True, default=_temp_slug
    )
    name: Mapped[str] = mapped_column(
        String(64), nullable=False
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="active"
    )
    role_id: Mapped[int] = mapped_column(
        ForeignKey("roles.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    role: Mapped["Role"] = relationship("Role", back_populates="personas")
    agents: Mapped[list["Agent"]] = relationship("Agent", back_populates="persona")

    def generate_slug(self) -> str:
        """Generate slug from role name, persona name, and id.

        Format: {role_name}-{persona_name}-{id}, all lowercase.
        """
        return f"{self.role.name.lower()}-{self.name.lower()}-{self.id}"

    def __repr__(self) -> str:
        return f"<Persona id={self.id} slug={self.slug} name={self.name}>"


@event.listens_for(Persona, "after_insert")
def _set_persona_slug(mapper, connection, target):
    """Replace the temporary slug with the real one after insert provides the id."""
    slug = f"{target.role.name.lower()}-{target.name.lower()}-{target.id}"
    connection.execute(
        Persona.__table__.update()
        .where(Persona.__table__.c.id == target.id)
        .values(slug=slug)
    )
    target.slug = slug
