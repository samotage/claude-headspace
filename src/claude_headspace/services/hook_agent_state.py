"""Thread-safe state management for hook receiver per-agent state.

Encapsulates all mutable per-agent state dicts that were previously
module-level globals in hook_receiver.py. Uses a single threading.Lock
to protect all dicts, since they are correlated (e.g., session_end
clears multiple dicts atomically) and hold times are microsecond-level.

This follows the same locking pattern used by Broadcaster and SessionRegistry.
"""

import logging
import threading
import time

logger = logging.getLogger(__name__)

# How long (seconds) a respond-pending flag remains valid.
_RESPOND_PENDING_TTL = 10.0
_RESPOND_INFLIGHT_TTL = 10.0


class AgentHookState:
    """Thread-safe container for per-agent hook state.

    Singleton accessed via get_agent_hook_state(). All public methods
    acquire the internal lock to guarantee atomicity.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()

        # Track which tool triggered AWAITING_INPUT per agent
        self._awaiting_tool: dict[int, str | None] = {}

        # Track agents that just received a respond via the dashboard tmux bridge.
        # Value is time.time() when the flag was set.
        self._respond_pending: dict[int, float] = {}

        # Track agents with an in-flight voice/respond send (pre-commit).
        # Set before tmux send, cleared when respond_pending is set (after commit).
        # Value is time.time() when the flag was set.
        self._respond_inflight: dict[int, float] = {}

        # Track agents with an in-flight deferred stop thread
        self._deferred_stop_pending: set[int] = set()

        # Track per-agent transcript file position for incremental reading
        self._transcript_positions: dict[int, int] = {}

        # Track text of PROGRESS turns captured during the current agent response
        self._progress_texts: dict[int, list[str]] = {}

        # Track file metadata for IDLE-state file uploads via voice bridge
        self._file_metadata_pending: dict[int, dict] = {}

    # ── Awaiting Tool ────────────────────────────────────────────────

    def set_awaiting_tool(self, agent_id: int, tool_name: str) -> None:
        with self._lock:
            self._awaiting_tool[agent_id] = tool_name

    def get_awaiting_tool(self, agent_id: int) -> str | None:
        with self._lock:
            return self._awaiting_tool.get(agent_id)

    def clear_awaiting_tool(self, agent_id: int) -> str | None:
        with self._lock:
            return self._awaiting_tool.pop(agent_id, None)

    # ── Respond Pending ──────────────────────────────────────────────

    def set_respond_pending(self, agent_id: int) -> None:
        with self._lock:
            self._respond_pending[agent_id] = time.time()
            self._respond_inflight.pop(agent_id, None)  # Upgrade: inflight → pending

    def consume_respond_pending(self, agent_id: int) -> bool:
        """Atomically check, validate TTL, and clear respond-pending flag.

        Returns True if the flag was set and still within TTL.
        """
        with self._lock:
            ts = self._respond_pending.pop(agent_id, None)
            if ts is None:
                return False
            return (time.time() - ts) < _RESPOND_PENDING_TTL

    def is_respond_pending(self, agent_id: int) -> bool:
        """Non-consuming check: is a respond pending within TTL?

        Unlike consume_respond_pending, this does NOT remove the flag.
        This allows the flag to suppress multiple user_prompt_submit hooks
        within the TTL window — important because slash commands trigger
        a second hook when the Skill tool expands the command content.
        """
        with self._lock:
            ts = self._respond_pending.get(agent_id)
            if ts is None:
                return False
            if (time.time() - ts) >= _RESPOND_PENDING_TTL:
                # Expired — clean up
                del self._respond_pending[agent_id]
                return False
            return True

    # ── Respond Inflight ─────────────────────────────────────────────

    def set_respond_inflight(self, agent_id: int) -> None:
        """Mark that a voice/respond send is in-flight (pre-commit).

        Set before the tmux send so the hook knows to skip turn creation
        even before respond_pending is set (which happens after commit).
        """
        with self._lock:
            self._respond_inflight[agent_id] = time.time()

    def is_respond_inflight(self, agent_id: int) -> bool:
        """Check if a respond is in-flight (with TTL)."""
        with self._lock:
            ts = self._respond_inflight.get(agent_id)
            if ts is None:
                return False
            return (time.time() - ts) < _RESPOND_INFLIGHT_TTL

    def clear_respond_inflight(self, agent_id: int) -> None:
        with self._lock:
            self._respond_inflight.pop(agent_id, None)

    # ── Deferred Stop ────────────────────────────────────────────────

    def try_claim_deferred_stop(self, agent_id: int) -> bool:
        """Atomically try to claim a deferred stop slot.

        Returns True if the slot was available and is now claimed.
        Returns False if a deferred stop is already pending for this agent.
        """
        with self._lock:
            if agent_id in self._deferred_stop_pending:
                return False
            self._deferred_stop_pending.add(agent_id)
            return True

    def release_deferred_stop(self, agent_id: int) -> None:
        with self._lock:
            self._deferred_stop_pending.discard(agent_id)

    def is_deferred_stop_pending(self, agent_id: int) -> bool:
        with self._lock:
            return agent_id in self._deferred_stop_pending

    # ── Transcript Positions ─────────────────────────────────────────

    def get_transcript_position(self, agent_id: int) -> int | None:
        with self._lock:
            return self._transcript_positions.get(agent_id)

    def set_transcript_position(self, agent_id: int, position: int) -> None:
        with self._lock:
            self._transcript_positions[agent_id] = position

    def clear_transcript_position(self, agent_id: int) -> int | None:
        with self._lock:
            return self._transcript_positions.pop(agent_id, None)

    # ── Progress Texts ───────────────────────────────────────────────

    def append_progress_text(self, agent_id: int, text: str) -> None:
        with self._lock:
            if agent_id not in self._progress_texts:
                self._progress_texts[agent_id] = []
            self._progress_texts[agent_id].append(text)

    def consume_progress_texts(self, agent_id: int) -> list[str] | None:
        """Atomically pop and return all progress texts for an agent."""
        with self._lock:
            return self._progress_texts.pop(agent_id, None)

    def get_progress_texts(self, agent_id: int) -> list[str]:
        """Return a copy of progress texts (non-destructive)."""
        with self._lock:
            return list(self._progress_texts.get(agent_id, []))

    def clear_progress_texts(self, agent_id: int) -> None:
        with self._lock:
            self._progress_texts.pop(agent_id, None)

    # ── File Metadata Pending ────────────────────────────────────────

    def set_file_metadata_pending(self, agent_id: int, metadata: dict) -> None:
        with self._lock:
            self._file_metadata_pending[agent_id] = metadata

    def consume_file_metadata_pending(self, agent_id: int) -> dict | None:
        """Atomically pop and return pending file metadata."""
        with self._lock:
            return self._file_metadata_pending.pop(agent_id, None)

    # ── Lifecycle (bulk operations) ──────────────────────────────────

    def on_session_start(self, agent_id: int) -> None:
        """Clear session-scoped state for a new session."""
        with self._lock:
            self._transcript_positions.pop(agent_id, None)
            self._progress_texts.pop(agent_id, None)

    def on_session_end(self, agent_id: int) -> None:
        """Clear all per-agent state when a session ends."""
        with self._lock:
            self._awaiting_tool.pop(agent_id, None)
            self._respond_inflight.pop(agent_id, None)
            self._transcript_positions.pop(agent_id, None)
            self._progress_texts.pop(agent_id, None)

    def on_new_response_cycle(self, agent_id: int) -> None:
        """Clear state for a new user→agent response cycle."""
        with self._lock:
            self._awaiting_tool.pop(agent_id, None)
            self._progress_texts.pop(agent_id, None)

    # ── Testing ──────────────────────────────────────────────────────

    def reset(self) -> None:
        """Clear all state. Used by tests and reset_receiver_state()."""
        with self._lock:
            self._awaiting_tool.clear()
            self._respond_pending.clear()
            self._respond_inflight.clear()
            self._deferred_stop_pending.clear()
            self._transcript_positions.clear()
            self._progress_texts.clear()
            self._file_metadata_pending.clear()


# ── Module-level singleton ───────────────────────────────────────────

_instance: AgentHookState | None = None
_instance_lock = threading.Lock()


def get_agent_hook_state() -> AgentHookState:
    """Get or create the global AgentHookState singleton."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = AgentHookState()
    return _instance


def reset_agent_hook_state() -> None:
    """Reset the global singleton. For testing only."""
    global _instance
    with _instance_lock:
        if _instance is not None:
            _instance.reset()
        _instance = AgentHookState()
