"""PersonaType model — lookup table for persona classification."""

from typing import TYPE_CHECKING

from sqlalchemy import String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import db

if TYPE_CHECKING:
    from .persona import Persona


class PersonaType(db.Model):
    """
    Lookup table classifying personas into quadrants.

    2x2 matrix: type_key (agent/person) x subtype (internal/external).
    Four rows seeded by migration, never modified at runtime.

    Quadrants:
        id=1: agent/internal  — AI agents running on operator hardware
        id=2: agent/external  — AI agents from external collaborators (v2)
        id=3: person/internal — Human operator (Sam)
        id=4: person/external — External human collaborators (v2)
    """

    __tablename__ = "persona_types"
    __table_args__ = (
        UniqueConstraint("type_key", "subtype", name="uq_persona_type_key_subtype"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    type_key: Mapped[str] = mapped_column(
        String(16), nullable=False
    )
    subtype: Mapped[str] = mapped_column(
        String(16), nullable=False
    )

    # Relationships
    personas: Mapped[list["Persona"]] = relationship(
        "Persona", back_populates="persona_type"
    )

    def __repr__(self) -> str:
        return f"<PersonaType id={self.id} type_key={self.type_key} subtype={self.subtype}>"
