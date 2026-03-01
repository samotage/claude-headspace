"""Thread-safe state management for hook receiver per-agent state.

Encapsulates all mutable per-agent state dicts that were previously
module-level globals in hook_receiver.py. Uses a single threading.Lock
to protect all dicts, since they are correlated (e.g., session_end
clears multiple dicts atomically) and hold times are microsecond-level.

This follows the same locking pattern used by Broadcaster and SessionRegistry.
"""

import hashlib
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

        # Per-agent locks for progress capture atomicity.
        # Unlike _lock (which protects dict operations), these wrap the entire
        # read-position/read-JSONL/check-hash/create-Turn flow to prevent
        # TOCTOU races between concurrent hooks for the same agent.
        self._progress_capture_locks: dict[int, threading.Lock] = {}

        # Track file metadata for IDLE-state file uploads via voice bridge
        self._file_metadata_pending: dict[int, dict] = {}

        # Track agents with a pending skill injection whose priming
        # user_prompt_submit should be marked is_internal=True.
        self._skill_injection_pending: set[int] = set()

        # Content dedup: recent prompt hashes per agent for detecting
        # duplicate user_prompt_submit hooks (e.g. Claude Code firing
        # the same persona text 395 times).
        # dict[agent_id, list[tuple[hash_hex, timestamp]]]
        self._recent_prompt_hashes: dict[int, list[tuple[str, float]]] = {}

        # Command creation rate limiting: timestamps of recent command
        # creations per agent.  Prevents blast radius when dedup misses.
        # dict[agent_id, list[float]]
        self._command_creation_times: dict[int, list[float]] = {}

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

    # ── Progress Capture Locks ────────────────────────────────────────

    def get_progress_capture_lock(self, agent_id: int) -> threading.Lock:
        """Get or create a per-agent lock for progress capture atomicity.

        Serialises the entire read-position → read-JSONL → check-hash →
        create-Turn flow within _capture_progress_text_impl so concurrent
        hooks for the same agent cannot create duplicate PROGRESS turns.
        """
        with self._lock:
            if agent_id not in self._progress_capture_locks:
                self._progress_capture_locks[agent_id] = threading.Lock()
            return self._progress_capture_locks[agent_id]

    # ── File Metadata Pending ────────────────────────────────────────

    def set_file_metadata_pending(self, agent_id: int, metadata: dict) -> None:
        with self._lock:
            self._file_metadata_pending[agent_id] = metadata

    def consume_file_metadata_pending(self, agent_id: int) -> dict | None:
        """Atomically pop and return pending file metadata."""
        with self._lock:
            return self._file_metadata_pending.pop(agent_id, None)

    # ── Skill Injection Pending ─────────────────────────────────────

    def set_skill_injection_pending(self, agent_id: int) -> None:
        """Mark that a skill injection was just sent to this agent.

        The next user_prompt_submit for this agent is the priming message
        echoed back by Claude Code and should be marked is_internal=True.
        """
        with self._lock:
            self._skill_injection_pending.add(agent_id)

    def consume_skill_injection_pending(self, agent_id: int) -> bool:
        """Atomically check and clear the skill injection pending flag.

        Returns True if the flag was set (and is now cleared).
        """
        with self._lock:
            if agent_id in self._skill_injection_pending:
                self._skill_injection_pending.discard(agent_id)
                return True
            return False

    # ── Content Dedup ─────────────────────────────────────────────────
    # Defence-in-depth against Claude Code's spurious hook firing.
    # Tracks sha256 hashes of recent prompts per agent with a 30s window.

    _DEDUP_WINDOW_SECONDS = 30.0
    _DEDUP_MAX_HISTORY = 5

    def is_duplicate_prompt(self, agent_id: int, text: str | None) -> bool:
        """Check if this prompt text was already seen within the dedup window.

        First occurrence records the hash and returns False.
        Subsequent identical prompts within 30s return True.

        Args:
            agent_id: The agent receiving the prompt
            text: The prompt text to check

        Returns:
            True if this is a duplicate (should be suppressed)
        """
        if not text:
            return False

        prompt_hash = hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:16]
        now = time.time()

        with self._lock:
            history = self._recent_prompt_hashes.get(agent_id, [])

            # Prune expired entries
            history = [(h, ts) for h, ts in history if (now - ts) < self._DEDUP_WINDOW_SECONDS]

            # Check for duplicate
            for h, _ts in history:
                if h == prompt_hash:
                    return True

            # Record this prompt
            history.append((prompt_hash, now))
            # Keep only the most recent entries
            if len(history) > self._DEDUP_MAX_HISTORY:
                history = history[-self._DEDUP_MAX_HISTORY:]

            self._recent_prompt_hashes[agent_id] = history
            return False

    # ── Command Rate Limiting ─────────────────────────────────────────
    # Caps blast radius even if dedup misses.
    # Max 5 commands per 10s per agent.

    _RATE_LIMIT_WINDOW_SECONDS = 10.0
    _RATE_LIMIT_MAX_COMMANDS = 5

    def is_command_rate_limited(self, agent_id: int) -> bool:
        """Check if command creation is rate-limited for this agent.

        Returns True if the agent has created >= max commands within the window.
        """
        now = time.time()
        with self._lock:
            times = self._command_creation_times.get(agent_id, [])
            # Prune expired
            times = [t for t in times if (now - t) < self._RATE_LIMIT_WINDOW_SECONDS]
            self._command_creation_times[agent_id] = times
            return len(times) >= self._RATE_LIMIT_MAX_COMMANDS

    def record_command_creation(self, agent_id: int) -> None:
        """Record a command creation timestamp for rate limiting."""
        now = time.time()
        with self._lock:
            times = self._command_creation_times.get(agent_id, [])
            times = [t for t in times if (now - t) < self._RATE_LIMIT_WINDOW_SECONDS]
            times.append(now)
            self._command_creation_times[agent_id] = times

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
            self._skill_injection_pending.discard(agent_id)
            self._recent_prompt_hashes.pop(agent_id, None)
            self._command_creation_times.pop(agent_id, None)
            self._progress_capture_locks.pop(agent_id, None)

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
            self._skill_injection_pending.clear()
            self._recent_prompt_hashes.clear()
            self._command_creation_times.clear()
            self._progress_capture_locks.clear()


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
