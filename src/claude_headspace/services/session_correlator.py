"""Session correlator for matching Claude Code sessions to agents."""

import logging
import time
from datetime import datetime, timezone
from typing import NamedTuple
from uuid import UUID, uuid4

from ..database import db
from ..models.agent import Agent
from ..models.project import Project

logger = logging.getLogger(__name__)


class CorrelationResult(NamedTuple):
    """Result of session correlation."""

    agent: Agent
    is_new: bool
    correlation_method: str  # "session_id", "working_directory", "created"


class CacheEntry(NamedTuple):
    """Cache entry with timestamp for TTL support."""

    agent_id: int
    cached_at: float


# WARNING: This in-memory cache is process-local. In multi-process deployments
# (gunicorn with multiple workers), each process has its own cache.
# For production, replace with Redis or database-backed cache.
_session_cache: dict[str, CacheEntry] = {}
CACHE_TTL_SECONDS = 3600  # 1 hour


def _cleanup_stale_cache_entries() -> None:
    """Remove cache entries older than TTL."""
    now = time.time()
    stale_keys = [
        key for key, entry in _session_cache.items()
        if now - entry.cached_at > CACHE_TTL_SECONDS
    ]
    for key in stale_keys:
        del _session_cache[key]
    if stale_keys:
        logger.debug(f"Cleaned up {len(stale_keys)} stale cache entries")


def correlate_session(
    claude_session_id: str,
    working_directory: str | None = None,
) -> CorrelationResult:
    """
    Correlate a Claude Code session to an agent.

    Correlation strategy:
    1. Check if Claude session ID has been seen before (cache lookup)
    2. Match by working directory to existing agents
    3. Create new agent if no match found

    Args:
        claude_session_id: The Claude Code session ID
        working_directory: The working directory of the session

    Returns:
        CorrelationResult with the matched or created agent
    """
    # Cleanup stale cache entries periodically
    _cleanup_stale_cache_entries()

    # Strategy 1: Check session cache
    if claude_session_id in _session_cache:
        agent_id = _session_cache[claude_session_id].agent_id
        agent = db.session.get(Agent, agent_id)
        if agent:
            logger.debug(
                f"Session {claude_session_id} matched to agent {agent_id} via cache"
            )
            return CorrelationResult(
                agent=agent,
                is_new=False,
                correlation_method="session_id",
            )
        # Agent no longer exists, remove from cache
        del _session_cache[claude_session_id]

    # Strategy 2: Match by working directory
    if working_directory:
        project = (
            db.session.query(Project)
            .filter(Project.path == working_directory)
            .first()
        )
        if project:
            # Find most recent active agent for this project
            agent = (
                db.session.query(Agent)
                .filter(Agent.project_id == project.id)
                .order_by(Agent.last_seen_at.desc())
                .first()
            )
            if agent:
                # Cache the session ID -> agent mapping
                _session_cache[claude_session_id] = CacheEntry(agent.id, time.time())
                logger.debug(
                    f"Session {claude_session_id} matched to agent {agent.id} "
                    f"via working directory {working_directory}"
                )
                return CorrelationResult(
                    agent=agent,
                    is_new=False,
                    correlation_method="working_directory",
                )

    # Strategy 3: Create new agent
    agent, project = _create_agent_for_session(claude_session_id, working_directory)

    # Cache the new mapping
    _session_cache[claude_session_id] = CacheEntry(agent.id, time.time())

    logger.info(
        f"Created new agent {agent.id} for session {claude_session_id} "
        f"in project {project.name}"
    )
    return CorrelationResult(
        agent=agent,
        is_new=True,
        correlation_method="created",
    )


def _create_agent_for_session(
    claude_session_id: str,
    working_directory: str | None,
) -> tuple[Agent, Project]:
    """
    Create a new agent for a Claude Code session.

    Args:
        claude_session_id: The Claude Code session ID
        working_directory: The working directory (optional)

    Returns:
        Tuple of (agent, project)
    """
    # Find or create project
    if working_directory:
        project = (
            db.session.query(Project)
            .filter(Project.path == working_directory)
            .first()
        )
        if not project:
            # Extract project name from path
            project_name = working_directory.rstrip("/").split("/")[-1]
            project = Project(
                name=project_name,
                path=working_directory,
            )
            db.session.add(project)
            db.session.flush()  # Get project ID
    else:
        # Create placeholder project for unknown sessions
        project = Project(
            name=f"unknown-{claude_session_id[:8]}",
            path=f"__unknown__/{claude_session_id}",  # Unique placeholder path
        )
        db.session.add(project)
        db.session.flush()

    # Create agent
    agent = Agent(
        session_uuid=uuid4(),
        project_id=project.id,
        started_at=datetime.now(timezone.utc),
        last_seen_at=datetime.now(timezone.utc),
    )
    db.session.add(agent)
    db.session.commit()

    return agent, project


def clear_session_cache() -> None:
    """Clear the session correlation cache."""
    global _session_cache
    _session_cache = {}
    logger.debug("Session correlation cache cleared")


def get_cached_agent_id(claude_session_id: str) -> int | None:
    """
    Get the cached agent ID for a Claude session ID.

    Args:
        claude_session_id: The Claude Code session ID

    Returns:
        Agent ID if cached, None otherwise
    """
    entry = _session_cache.get(claude_session_id)
    return entry.agent_id if entry else None


def cache_session_mapping(claude_session_id: str, agent_id: int) -> None:
    """
    Manually cache a session ID to agent mapping.

    Args:
        claude_session_id: The Claude Code session ID
        agent_id: The agent database ID
    """
    _session_cache[claude_session_id] = CacheEntry(agent_id, time.time())
    logger.debug(f"Cached session {claude_session_id} -> agent {agent_id}")
