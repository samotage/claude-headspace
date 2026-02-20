"""Organisation model."""

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import db

if TYPE_CHECKING:
    from .position import Position


class Organisation(db.Model):
    """
    Represents an organisational grouping.

    In v1, this table holds a single record (the development org). It exists
    as infrastructure for future multi-org capability — Position records will
    reference Organisation via a foreign key.
    """

    __tablename__ = "organisations"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(
        String(128), nullable=False
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="active"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    positions: Mapped[list["Position"]] = relationship(
        "Position", back_populates="organisation"
    )

    def __repr__(self) -> str:
        return f"<Organisation id={self.id} name={self.name} status={self.status}>"
