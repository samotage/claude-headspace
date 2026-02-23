"""Position model."""

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import db

if TYPE_CHECKING:
    from .organisation import Organisation
    from .role import Role


class Position(db.Model):
    """
    Represents a seat in an organisational chart.

    Each position belongs to one Organisation, requires one Role, and optionally
    reports to and escalates to other positions in the same hierarchy. The dual
    self-referential foreign keys support separate reporting and escalation paths.
    """

    __tablename__ = "positions"

    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column(
        ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False
    )
    role_id: Mapped[int] = mapped_column(
        ForeignKey("roles.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(
        String(128), nullable=False
    )
    reports_to_id: Mapped[int | None] = mapped_column(
        ForeignKey("positions.id", ondelete="SET NULL"), nullable=True
    )
    escalates_to_id: Mapped[int | None] = mapped_column(
        ForeignKey("positions.id", ondelete="SET NULL"), nullable=True
    )
    level: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    is_cross_cutting: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    # Relationships — external FKs
    organisation: Mapped["Organisation"] = relationship(
        "Organisation", back_populates="positions"
    )
    role: Mapped["Role"] = relationship(
        "Role", back_populates="positions"
    )

    # Relationships — self-referential
    reports_to: Mapped["Position | None"] = relationship(
        "Position",
        remote_side="Position.id",
        foreign_keys=[reports_to_id],
        back_populates="direct_reports",
    )
    escalates_to: Mapped["Position | None"] = relationship(
        "Position",
        remote_side="Position.id",
        foreign_keys=[escalates_to_id],
    )
    direct_reports: Mapped[list["Position"]] = relationship(
        "Position",
        foreign_keys=[reports_to_id],
        back_populates="reports_to",
    )

    def __repr__(self) -> str:
        return f"<Position id={self.id} title={self.title} level={self.level}>"
