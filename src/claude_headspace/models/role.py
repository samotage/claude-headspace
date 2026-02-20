"""Role model."""

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import db

if TYPE_CHECKING:
    from .persona import Persona


class Role(db.Model):
    """
    Represents an agent specialisation (e.g., developer, tester, pm, architect).

    Role is a shared lookup table defining the vocabulary of specialisations
    referenced by Persona records and, in future sprints, Position records.
    """

    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    personas: Mapped[list["Persona"]] = relationship(
        "Persona", back_populates="role"
    )

    def __repr__(self) -> str:
        return f"<Role id={self.id} name={self.name}>"
