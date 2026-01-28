"""Project model."""

from datetime import datetime, timezone

from sqlalchemy import Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import db


class Project(db.Model):
    """
    Represents a monitored project/codebase.

    Projects are auto-discovered from the filesystem and may have
    associated GitHub repository information.
    """

    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(nullable=False)
    path: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    github_repo: Mapped[str | None] = mapped_column(Text, nullable=True)
    current_branch: Mapped[str | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    agents: Mapped[list["Agent"]] = relationship(
        "Agent", back_populates="project", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Project id={self.id} name={self.name}>"
