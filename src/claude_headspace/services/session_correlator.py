"""Session correlator for matching Claude Code sessions to agents."""

import logging
import os
import threading
import time
from datetime import datetime, timezone
from typing import NamedTuple
from uuid import UUID, uuid4

from sqlalchemy import text

from ..database import db
from ..models.agent import Agent
from ..models.project import Project

logger = logging.getLogger(__name__)

# Default query timeout in milliseconds for database operations
DEFAULT_QUERY_TIMEOUT_MS = 10000  # 10 seconds

# Project root markers — if any of these exist in a directory, it's a project root
_PROJECT_ROOT_MARKERS = (
    ".git",
    "pyproject.toml",
    "package.json",
    "Cargo.toml",
    "go.mod",
    "Makefile",
    "setup.py",
    "setup.cfg",
    ".project",
)

# Directory prefixes that are never valid projects
_REJECTED_PREFIXES = (
    "/tmp",
    "/private/tmp",
    "/var",
)


class CorrelationResult(NamedTuple):
    """Result of session correlation."""

    agent: Agent
    is_new: bool
    correlation_method: str  # "session_id", "db_session_id", "headspace_session_id", "working_directory", "created"


class CacheEntry(NamedTuple):
    """Cache entry with timestamp for TTL support."""

    agent_id: int
    cached_at: float


# WARNING: This in-memory cache is process-local. In multi-process deployments
# (gunicorn with multiple workers), each process has its own cache.
# For production, replace with Redis or database-backed cache.
_session_cache: dict[str, CacheEntry] = {}
_session_cache_lock = threading.Lock()
CACHE_TTL_SECONDS = 3600  # 1 hour


def _cleanup_stale_cache_entries() -> None:
    """Remove cache entries older than TTL. Must be called with _session_cache_lock held."""
    now = time.time()
    stale_keys = [
        key for key, entry in _session_cache.items()
        if now - entry.cached_at > CACHE_TTL_SECONDS
    ]
    for key in stale_keys:
        del _session_cache[key]
    if stale_keys:
        logger.debug(f"Cleaned up {len(stale_keys)} stale cache entries")


def _cache_get(key: str) -> CacheEntry | None:
    """Thread-safe cache lookup."""
    with _session_cache_lock:
        return _session_cache.get(key)


def _cache_set(key: str, agent_id: int) -> None:
    """Thread-safe cache write."""
    with _session_cache_lock:
        _session_cache[key] = CacheEntry(agent_id, time.time())


def _cache_delete(key: str) -> None:
    """Thread-safe cache removal."""
    with _session_cache_lock:
        _session_cache.pop(key, None)


def _cache_cleanup() -> None:
    """Thread-safe cache cleanup."""
    with _session_cache_lock:
        _cleanup_stale_cache_entries()


def _reactivate_if_ended(agent: Agent) -> bool:
    """Clear ended_at if the agent was reaped/ended, reactivating it.

    Called when a hook arrives for a previously-ended agent, proving the
    Claude Code session is still alive.

    Returns True if the agent was reactivated.
    """
    if agent.ended_at is None:
        return False

    agent.ended_at = None
    agent.last_seen_at = datetime.now(timezone.utc)
    db.session.commit()

    # Notify clients that the agent is active again (lazy import to avoid circular deps)
    try:
        from .card_state import broadcast_card_refresh
        broadcast_card_refresh(agent, "reactivated")
    except Exception:
        pass  # Best-effort; hook processor will broadcast again shortly

    logger.info(
        f"Reactivated ended agent {agent.id} (session_uuid={agent.session_uuid}) "
        f"— hook arrived for previously reaped/ended agent"
    )
    return True


def _is_rejected_directory(path: str) -> bool:
    """
    Check if a path is a known non-project directory that should be rejected.

    Rejects:
    - Paths under /tmp, /private/tmp, /var
    - The global ~/.claude directory
    """
    normalized = os.path.normpath(path)

    for prefix in _REJECTED_PREFIXES:
        if normalized == prefix or normalized.startswith(prefix + "/"):
            return True

    # Reject the global ~/.claude directory (but NOT a .claude subdir inside a project)
    home = os.path.expanduser("~")
    global_claude = os.path.join(home, ".claude")
    if normalized == global_claude or normalized.startswith(global_claude + "/"):
        return True

    return False


def _resolve_project_root(path: str) -> str:
    """
    Walk up from the given path to find the actual project root.

    Looks for project root markers (.git, pyproject.toml, etc.) going upward.
    If a marker is found, returns that directory. Otherwise returns the
    original path (it may still be a valid project without markers).

    This handles the case where cwd is a subdirectory like:
    /Users/sam/dev/myproject/.claude -> resolves to /Users/sam/dev/myproject
    /Users/sam/dev/myproject/src/lib -> resolves to /Users/sam/dev/myproject
    """
    normalized = os.path.normpath(path)
    current = normalized

    while True:
        for marker in _PROJECT_ROOT_MARKERS:
            if os.path.exists(os.path.join(current, marker)):
                if current != normalized:
                    logger.debug(
                        f"Resolved project root: {normalized} -> {current}"
                    )
                return current

        parent = os.path.dirname(current)
        if parent == current:
            # Reached filesystem root without finding a marker
            break
        current = parent

    # No marker found — return the original path
    return normalized


def _resolve_working_directory(working_directory: str | None) -> str | None:
    """
    Validate and resolve a working directory to a project root.

    Returns None if the directory is a known non-project path.
    Otherwise resolves upward to find the actual project root.
    """
    if not working_directory:
        return None

    if _is_rejected_directory(working_directory):
        logger.info(
            f"Rejected non-project working directory: {working_directory}"
        )
        return None

    resolved = _resolve_project_root(working_directory)

    # After resolution, check again — the resolved path might also be rejected
    if _is_rejected_directory(resolved):
        logger.info(
            f"Rejected resolved directory: {working_directory} -> {resolved}"
        )
        return None

    return resolved


def _set_query_timeout(timeout_ms: int = DEFAULT_QUERY_TIMEOUT_MS) -> None:
    """Set PostgreSQL statement_timeout for the current session."""
    try:
        db.session.execute(text(f"SET LOCAL statement_timeout = '{timeout_ms}'"))
    except Exception as e:
        logger.debug(f"Could not set statement_timeout (non-fatal): {e}")


def correlate_session(
    claude_session_id: str,
    working_directory: str | None = None,
    headspace_session_id: str | None = None,
    query_timeout_ms: int = DEFAULT_QUERY_TIMEOUT_MS,
) -> CorrelationResult:
    """
    Correlate a Claude Code session to an agent.

    Correlation strategy:
    1. Check in-memory cache (fast path)
    2. Check database by claude_session_id (survives server restarts)
    2.5. Match by headspace_session_id → Agent.session_uuid (CLI-created agents)
    3. Match by working directory to existing project/agents (unclaimed only)
    4. Create new agent — only if we have a valid working directory

    Args:
        claude_session_id: The Claude Code session ID
        working_directory: The working directory of the session
        headspace_session_id: The CLI-assigned session UUID from
            CLAUDE_HEADSPACE_SESSION_ID env var

    Returns:
        CorrelationResult with the matched or created agent

    Raises:
        ValueError: If session cannot be correlated (no working directory
                    and not previously seen)
    """
    # Cleanup stale cache entries periodically
    _cache_cleanup()

    # Set query timeout to prevent long-running DB queries from blocking hooks
    _set_query_timeout(query_timeout_ms)

    # Strategy 1: Check in-memory session cache — working_directory is ignored
    # for already-known sessions. The project was determined at first contact.
    cached = _cache_get(claude_session_id)
    if cached is not None:
        agent = db.session.get(Agent, cached.agent_id)
        if agent:
            _reactivate_if_ended(agent)
            logger.debug(
                f"Session {claude_session_id} matched to agent {cached.agent_id} via cache"
            )
            return CorrelationResult(
                agent=agent,
                is_new=False,
                correlation_method="session_id",
            )
        # Agent no longer exists, remove from cache
        _cache_delete(claude_session_id)

    # Strategy 2: Check database by claude_session_id — this survives server
    # restarts where the in-memory cache is lost
    agent = (
        db.session.query(Agent)
        .filter(Agent.claude_session_id == claude_session_id)
        .first()
    )
    if agent:
        _reactivate_if_ended(agent)
        # Re-populate the in-memory cache
        _cache_set(claude_session_id, agent.id)
        logger.debug(
            f"Session {claude_session_id} matched to agent {agent.id} via DB lookup"
        )
        return CorrelationResult(
            agent=agent,
            is_new=False,
            correlation_method="db_session_id",
        )

    # Strategy 2.5: Match by headspace_session_id → Agent.session_uuid
    # The CLI wrapper creates agents with session_uuid and sets
    # CLAUDE_HEADSPACE_SESSION_ID in the env. The hook script forwards this
    # as headspace_session_id. This bridges the CLI UUID to Claude Code's
    # internal session_id.
    if headspace_session_id:
        try:
            target_uuid = UUID(headspace_session_id)
        except ValueError:
            logger.warning(
                f"Invalid headspace_session_id UUID: {headspace_session_id}"
            )
        else:
            agent = (
                db.session.query(Agent)
                .filter(Agent.session_uuid == target_uuid)
                .first()
            )
            if agent:
                dirty = False

                # Link or update claude_session_id
                if agent.claude_session_id != claude_session_id:
                    old_id = agent.claude_session_id
                    agent.claude_session_id = claude_session_id
                    dirty = True
                    logger.info(
                        f"Linked claude_session_id={claude_session_id} to "
                        f"agent {agent.id} (session_uuid={headspace_session_id})"
                        f"{f', replacing {old_id}' if old_id else ''}"
                    )

                # Reactivate if ended; _reactivate_if_ended commits
                # (which also flushes any claude_session_id change above)
                if not _reactivate_if_ended(agent) and dirty:
                    db.session.commit()

                # Cache for fast path on subsequent hooks
                _cache_set(claude_session_id, agent.id)
                logger.debug(
                    f"Session {claude_session_id} matched to agent {agent.id} "
                    f"via headspace_session_id {headspace_session_id}"
                )
                return CorrelationResult(
                    agent=agent,
                    is_new=False,
                    correlation_method="headspace_session_id",
                )

    # Resolve working directory to project root, filtering out junk paths
    resolved_directory = _resolve_working_directory(working_directory)
    if working_directory and not resolved_directory:
        logger.debug(
            f"Working directory {working_directory} was rejected/unresolvable, "
            f"proceeding without it"
        )

    # Strategy 3: Match by working directory — only unclaimed, active agents.
    # An agent is "unclaimed" if claude_session_id is NULL (not yet linked to
    # a Claude Code session). Excluding ended agents prevents stealing from
    # sessions that have already finished.
    if resolved_directory:
        project = (
            db.session.query(Project)
            .filter(Project.path == resolved_directory)
            .first()
        )
        if project:
            # Find most recent active, unclaimed agent for this project
            agent = (
                db.session.query(Agent)
                .filter(
                    Agent.project_id == project.id,
                    Agent.ended_at.is_(None),
                    Agent.claude_session_id.is_(None),
                )
                .order_by(Agent.last_seen_at.desc())
                .first()
            )
            if agent:
                # Claim this agent by setting claude_session_id
                agent.claude_session_id = claude_session_id
                db.session.commit()

                # Cache the session ID -> agent mapping
                _cache_set(claude_session_id, agent.id)
                logger.debug(
                    f"Session {claude_session_id} matched to agent {agent.id} "
                    f"via working directory {resolved_directory} (claimed)"
                )
                return CorrelationResult(
                    agent=agent,
                    is_new=False,
                    correlation_method="working_directory",
                )

    # Strategy 4: Create new agent — but ONLY with a valid working directory.
    # Never create garbage placeholder projects.
    if not resolved_directory:
        raise ValueError(
            f"Cannot correlate session {claude_session_id}: no valid working "
            f"directory (received: {working_directory!r}) and session not "
            f"previously seen. Hook events for unknown sessions without a "
            f"project directory are dropped."
        )

    agent, project = _create_agent_for_session(
        claude_session_id, resolved_directory
    )

    # Cache the new mapping
    _cache_set(claude_session_id, agent.id)

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
    working_directory: str,
) -> tuple[Agent, Project]:
    """
    Create a new agent for a Claude Code session.

    Args:
        claude_session_id: The Claude Code session ID
        working_directory: The resolved working directory (required)

    Returns:
        Tuple of (agent, project)
    """
    # Find registered project — auto-creation is disabled
    project = (
        db.session.query(Project)
        .filter(Project.path == working_directory)
        .first()
    )
    if not project:
        raise ValueError(
            f"Project not registered: '{working_directory}'. "
            f"Register this project at the /projects management page before starting a session."
        )

    # Create agent with persistent claude_session_id.
    # Use INSERT ... ON CONFLICT DO UPDATE on claude_session_id to handle
    # race conditions where concurrent hooks for the same session both try
    # to create an agent simultaneously (SRV-C4).
    now = datetime.now(timezone.utc)
    new_uuid = uuid4()

    try:
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        stmt = pg_insert(Agent).values(
            session_uuid=new_uuid,
            claude_session_id=claude_session_id,
            project_id=project.id,
            started_at=now,
            last_seen_at=now,
        )
        # If claude_session_id already exists (race), just update last_seen_at
        stmt = stmt.on_conflict_do_update(
            index_elements=["claude_session_id"],
            set_={"last_seen_at": now},
        )
        result = db.session.execute(stmt)
        db.session.commit()

        # Fetch the agent (either newly created or existing from race)
        agent = (
            db.session.query(Agent)
            .filter(Agent.claude_session_id == claude_session_id)
            .first()
        )
        if not agent:
            raise RuntimeError(f"Agent not found after upsert for session {claude_session_id}")

    except Exception as e:
        # Graceful fallback: if ON CONFLICT fails (e.g. no unique constraint
        # on claude_session_id yet — Agent D creates it separately), fall
        # back to the original insert-and-retry pattern.
        db.session.rollback()

        # Check if another process created it in the meantime
        agent = (
            db.session.query(Agent)
            .filter(Agent.claude_session_id == claude_session_id)
            .first()
        )
        if agent:
            logger.info(f"Agent already created by concurrent request for session {claude_session_id}")
            return agent, project

        # No race — create normally
        agent = Agent(
            session_uuid=new_uuid,
            claude_session_id=claude_session_id,
            project_id=project.id,
            started_at=now,
            last_seen_at=now,
        )
        db.session.add(agent)
        db.session.commit()

    return agent, project


def clear_session_cache() -> None:
    """Clear the session correlation cache."""
    with _session_cache_lock:
        _session_cache.clear()
    logger.debug("Session correlation cache cleared")


def get_cached_agent_id(claude_session_id: str) -> int | None:
    """
    Get the cached agent ID for a Claude session ID.

    Args:
        claude_session_id: The Claude Code session ID

    Returns:
        Agent ID if cached, None otherwise
    """
    entry = _cache_get(claude_session_id)
    return entry.agent_id if entry else None


def cache_session_mapping(claude_session_id: str, agent_id: int) -> None:
    """
    Manually cache a session ID to agent mapping.

    Args:
        claude_session_id: The Claude Code session ID
        agent_id: The agent database ID
    """
    _cache_set(claude_session_id, agent_id)
    logger.debug(f"Cached session {claude_session_id} -> agent {agent_id}")
