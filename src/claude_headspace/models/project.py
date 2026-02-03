"""Project model."""

import re
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Index, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import db


def generate_slug(name: str) -> str:
    """Generate a URL-safe slug from a project name.

    Lowercase, replace non-alphanumeric characters with hyphens,
    collapse multiple hyphens, strip leading/trailing hyphens.
    """
    slug = name.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    slug = slug.strip("-")
    return slug or "project"


class Project(db.Model):
    """
    Represents a monitored project/codebase.

    Projects are manually registered and may have
    associated GitHub repository information.
    """

    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(nullable=False)
    slug: Mapped[str] = mapped_column(nullable=False, unique=True, index=True)
    path: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    github_repo: Mapped[str | None] = mapped_column(Text, nullable=True)
    current_branch: Mapped[str | None] = mapped_column(nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    inference_paused: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    inference_paused_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    inference_paused_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    agents: Mapped[list["Agent"]] = relationship(
        "Agent", back_populates="project", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Project id={self.id} name={self.name}>"
