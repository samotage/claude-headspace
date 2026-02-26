"""ApiCallLog model for logging external API requests and responses."""

import enum
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..database import db


class AuthStatus(str, enum.Enum):
    """Authentication status for an API call."""

    AUTHENTICATED = "authenticated"
    FAILED = "failed"
    UNAUTHENTICATED = "unauthenticated"
    BYPASSED = "bypassed"


class ApiCallLog(db.Model):
    """
    Records external API requests and responses for debugging.

    Each record captures the full HTTP request/response cycle for
    external-facing API endpoints (remote agents, voice bridge, embed).
    """

    __tablename__ = "api_call_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )

    # HTTP request metadata
    http_method: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    endpoint_path: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    query_string: Mapped[str | None] = mapped_column(Text, nullable=True)
    request_content_type: Mapped[str | None] = mapped_column(String(200), nullable=True)
    request_headers: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    request_body: Mapped[str | None] = mapped_column(Text, nullable=True)

    # HTTP response metadata
    response_status_code: Mapped[int] = mapped_column(
        Integer, nullable=False, index=True
    )
    response_content_type: Mapped[str | None] = mapped_column(
        String(200), nullable=True
    )
    response_body: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Performance and source
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)

    # Authentication
    auth_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="unauthenticated", index=True
    )

    # FK design: SET NULL on delete -- API call logs have independent value
    # for debugging. Records are retained even when the parent entity is deleted.
    project_id: Mapped[int | None] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True
    )
    agent_id: Mapped[int | None] = mapped_column(
        ForeignKey("agents.id", ondelete="SET NULL"), nullable=True, index=True
    )

    def __repr__(self) -> str:
        return (
            f"<ApiCallLog id={self.id} {self.http_method} {self.endpoint_path} "
            f"status={self.response_status_code}>"
        )


# Composite index for common query pattern: filter by endpoint + sort by time
Index(
    "ix_api_call_logs_endpoint_timestamp",
    ApiCallLog.endpoint_path,
    ApiCallLog.timestamp.desc(),
)
