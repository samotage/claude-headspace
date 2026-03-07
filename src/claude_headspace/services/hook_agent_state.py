"""Thread-safe state management for hook receiver per-agent state.

Encapsulates all mutable per-agent state dicts that were previously
module-level globals in hook_receiver.py. Uses a single threading.Lock
to protect all dicts, since they are correlated (e.g., session_end
clears multiple dicts atomically) and hold times are microsecond-level.

Supports Redis-backed storage with in-memory fallback. When Redis is
available, state survives process restarts.
"""

import hashlib
import json
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

    When redis_manager is provided and available, state is mirrored to Redis.
    On Redis failure, falls back to in-memory state transparently.
    """

    def __init__(self, redis_manager=None) -> None:
        self._lock = threading.Lock()
        self._redis = redis_manager

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

    # ── Redis Helpers ────────────────────────────────────────────────

    def _redis_available(self) -> bool:
        return self._redis is not None and self._redis.is_available

    def _rkey(self, category: str, agent_id: int) -> str:
        """Build a Redis key for a per-agent state category."""
        return self._redis.key("hookstate", category, str(agent_id))

    def _rkey_set(self, category: str, agent_id: int) -> str:
        """Build a Redis key for a per-agent set category."""
        return self._redis.key("hookstate", "set", category, str(agent_id))

    # ── Awaiting Tool ────────────────────────────────────────────────

    def set_awaiting_tool(self, agent_id: int, tool_name: str) -> None:
        with self._lock:
            self._awaiting_tool[agent_id] = tool_name
        if self._redis_available():
            try:
                self._redis.set(
                    self._rkey("awaiting_tool", agent_id), tool_name, ex=86400
                )
            except Exception:
                pass

    def get_awaiting_tool(self, agent_id: int) -> str | None:
        if self._redis_available():
            try:
                val = self._redis.get(self._rkey("awaiting_tool", agent_id))
                if val is not None:
                    return val
            except Exception:
                pass
        with self._lock:
            return self._awaiting_tool.get(agent_id)

    def clear_awaiting_tool(self, agent_id: int) -> str | None:
        if self._redis_available():
            try:
                self._redis.delete(self._rkey("awaiting_tool", agent_id))
            except Exception:
                pass
        with self._lock:
            return self._awaiting_tool.pop(agent_id, None)

    # ── Respond Pending ──────────────────────────────────────────────

    def set_respond_pending(self, agent_id: int) -> None:
        now = time.time()
        with self._lock:
            self._respond_pending[agent_id] = now
            self._respond_inflight.pop(agent_id, None)  # Upgrade: inflight -> pending
        if self._redis_available():
            try:
                self._redis.set(
                    self._rkey("respond_pending", agent_id),
                    str(now),
                    ex=int(_RESPOND_PENDING_TTL),
                )
                self._redis.delete(self._rkey("respond_inflight", agent_id))
            except Exception:
                pass

    def consume_respond_pending(self, agent_id: int) -> bool:
        """Atomically check, validate TTL, and clear respond-pending flag."""
        if self._redis_available():
            try:
                key = self._rkey("respond_pending", agent_id)
                val = self._redis.get(key)
                if val is not None:
                    self._redis.delete(key)
                    ts = float(val)
                    with self._lock:
                        self._respond_pending.pop(agent_id, None)
                    return (time.time() - ts) < _RESPOND_PENDING_TTL
            except Exception:
                pass
        with self._lock:
            ts = self._respond_pending.pop(agent_id, None)
            if ts is None:
                return False
            return (time.time() - ts) < _RESPOND_PENDING_TTL

    def is_respond_pending(self, agent_id: int) -> bool:
        """Non-consuming check: is a respond pending within TTL?"""
        if self._redis_available():
            try:
                key = self._rkey("respond_pending", agent_id)
                val = self._redis.get(key)
                if val is not None:
                    ts = float(val)
                    if (time.time() - ts) < _RESPOND_PENDING_TTL:
                        return True
                    # Expired — clean up
                    self._redis.delete(key)
                    return False
            except Exception:
                pass
        with self._lock:
            ts = self._respond_pending.get(agent_id)
            if ts is None:
                return False
            if (time.time() - ts) >= _RESPOND_PENDING_TTL:
                del self._respond_pending[agent_id]
                return False
            return True

    # ── Respond Inflight ─────────────────────────────────────────────

    def set_respond_inflight(self, agent_id: int) -> None:
        now = time.time()
        with self._lock:
            self._respond_inflight[agent_id] = now
        if self._redis_available():
            try:
                self._redis.set(
                    self._rkey("respond_inflight", agent_id),
                    str(now),
                    ex=int(_RESPOND_INFLIGHT_TTL),
                )
            except Exception:
                pass

    def is_respond_inflight(self, agent_id: int) -> bool:
        if self._redis_available():
            try:
                val = self._redis.get(self._rkey("respond_inflight", agent_id))
                if val is not None:
                    return (time.time() - float(val)) < _RESPOND_INFLIGHT_TTL
            except Exception:
                pass
        with self._lock:
            ts = self._respond_inflight.get(agent_id)
            if ts is None:
                return False
            return (time.time() - ts) < _RESPOND_INFLIGHT_TTL

    def clear_respond_inflight(self, agent_id: int) -> None:
        if self._redis_available():
            try:
                self._redis.delete(self._rkey("respond_inflight", agent_id))
            except Exception:
                pass
        with self._lock:
            self._respond_inflight.pop(agent_id, None)

    # ── Deferred Stop ────────────────────────────────────────────────

    def try_claim_deferred_stop(self, agent_id: int) -> bool:
        if self._redis_available():
            try:
                key = self._rkey_set("deferred_stop", agent_id)
                # Use SET NX to atomically claim
                if self._redis.set_nx(key, "1", ex=300):
                    with self._lock:
                        self._deferred_stop_pending.add(agent_id)
                    return True
                return False
            except Exception:
                pass
        with self._lock:
            if agent_id in self._deferred_stop_pending:
                return False
            self._deferred_stop_pending.add(agent_id)
            return True

    def release_deferred_stop(self, agent_id: int) -> None:
        if self._redis_available():
            try:
                self._redis.delete(self._rkey_set("deferred_stop", agent_id))
            except Exception:
                pass
        with self._lock:
            self._deferred_stop_pending.discard(agent_id)

    def is_deferred_stop_pending(self, agent_id: int) -> bool:
        if self._redis_available():
            try:
                return self._redis.exists(self._rkey_set("deferred_stop", agent_id))
            except Exception:
                pass
        with self._lock:
            return agent_id in self._deferred_stop_pending

    # ── Transcript Positions ─────────────────────────────────────────

    def get_transcript_position(self, agent_id: int) -> int | None:
        if self._redis_available():
            try:
                val = self._redis.get(self._rkey("transcript_pos", agent_id))
                if val is not None:
                    return int(val)
            except Exception:
                pass
        with self._lock:
            return self._transcript_positions.get(agent_id)

    def set_transcript_position(self, agent_id: int, position: int) -> None:
        with self._lock:
            self._transcript_positions[agent_id] = position
        if self._redis_available():
            try:
                self._redis.set(
                    self._rkey("transcript_pos", agent_id), str(position), ex=86400
                )
            except Exception:
                pass

    def clear_transcript_position(self, agent_id: int) -> int | None:
        if self._redis_available():
            try:
                self._redis.delete(self._rkey("transcript_pos", agent_id))
            except Exception:
                pass
        with self._lock:
            return self._transcript_positions.pop(agent_id, None)

    # ── Progress Texts ───────────────────────────────────────────────

    def append_progress_text(self, agent_id: int, text: str) -> None:
        with self._lock:
            if agent_id not in self._progress_texts:
                self._progress_texts[agent_id] = []
            self._progress_texts[agent_id].append(text)
        if self._redis_available():
            try:
                key = self._rkey("progress_texts", agent_id)
                self._redis.lpush(key, text)
                self._redis.expire(key, 3600)
            except Exception:
                pass

    def consume_progress_texts(self, agent_id: int) -> list[str] | None:
        """Atomically pop and return all progress texts for an agent."""
        result = None
        if self._redis_available():
            try:
                key = self._rkey("progress_texts", agent_id)
                texts = []
                while True:
                    val = self._redis.rpop(key)
                    if val is None:
                        break
                    texts.append(val)
                if texts:
                    result = texts
            except Exception:
                pass
        with self._lock:
            mem_result = self._progress_texts.pop(agent_id, None)
        return result or mem_result

    def get_progress_texts(self, agent_id: int) -> list[str]:
        """Return a copy of progress texts (non-destructive)."""
        with self._lock:
            return list(self._progress_texts.get(agent_id, []))

    def clear_progress_texts(self, agent_id: int) -> None:
        if self._redis_available():
            try:
                self._redis.delete(self._rkey("progress_texts", agent_id))
            except Exception:
                pass
        with self._lock:
            self._progress_texts.pop(agent_id, None)

    # ── File Metadata Pending ────────────────────────────────────────

    def set_file_metadata_pending(self, agent_id: int, metadata: dict) -> None:
        with self._lock:
            self._file_metadata_pending[agent_id] = metadata
        if self._redis_available():
            try:
                key = self._rkey("file_meta", agent_id)
                self._redis.set_json(key, metadata)
                self._redis.expire(key, 86400)
            except Exception:
                pass

    def consume_file_metadata_pending(self, agent_id: int) -> dict | None:
        """Atomically pop and return pending file metadata."""
        if self._redis_available():
            try:
                key = self._rkey("file_meta", agent_id)
                val = self._redis.get_json(key)
                if val is not None:
                    self._redis.delete(key)
                    with self._lock:
                        self._file_metadata_pending.pop(agent_id, None)
                    return val
            except Exception:
                pass
        with self._lock:
            return self._file_metadata_pending.pop(agent_id, None)

    # ── Skill Injection Pending ─────────────────────────────────────

    def set_skill_injection_pending(self, agent_id: int) -> None:
        with self._lock:
            self._skill_injection_pending.add(agent_id)
        if self._redis_available():
            try:
                self._redis.set(self._rkey_set("skill_inject", agent_id), "1", ex=300)
            except Exception:
                pass

    def consume_skill_injection_pending(self, agent_id: int) -> bool:
        if self._redis_available():
            try:
                key = self._rkey_set("skill_inject", agent_id)
                if self._redis.exists(key):
                    self._redis.delete(key)
                    with self._lock:
                        self._skill_injection_pending.discard(agent_id)
                    return True
            except Exception:
                pass
        with self._lock:
            if agent_id in self._skill_injection_pending:
                self._skill_injection_pending.discard(agent_id)
                return True
            return False

    # ── Content Dedup ─────────────────────────────────────────────────

    _DEDUP_WINDOW_SECONDS = 30.0
    _DEDUP_MAX_HISTORY = 5

    def is_duplicate_prompt(self, agent_id: int, text: str | None) -> bool:
        """Check if this prompt text was already seen within the dedup window."""
        if not text:
            return False

        prompt_hash = hashlib.sha256(
            text.encode("utf-8", errors="replace")
        ).hexdigest()[:16]
        now = time.time()

        # Try Redis
        if self._redis_available():
            try:
                key = self._rkey("prompt_hashes", agent_id)
                raw = self._redis.get(key)
                history = json.loads(raw) if raw else []
                # Prune expired
                history = [
                    (h, ts)
                    for h, ts in history
                    if (now - ts) < self._DEDUP_WINDOW_SECONDS
                ]
                for h, _ts in history:
                    if h == prompt_hash:
                        return True
                history.append((prompt_hash, now))
                if len(history) > self._DEDUP_MAX_HISTORY:
                    history = history[-self._DEDUP_MAX_HISTORY :]
                self._redis.set(
                    key, json.dumps(history), ex=int(self._DEDUP_WINDOW_SECONDS * 2)
                )
                # Also update in-memory for fallback
                with self._lock:
                    self._recent_prompt_hashes[agent_id] = history
                return False
            except Exception:
                pass

        # In-memory fallback
        with self._lock:
            history = self._recent_prompt_hashes.get(agent_id, [])
            history = [
                (h, ts) for h, ts in history if (now - ts) < self._DEDUP_WINDOW_SECONDS
            ]
            for h, _ts in history:
                if h == prompt_hash:
                    return True
            history.append((prompt_hash, now))
            if len(history) > self._DEDUP_MAX_HISTORY:
                history = history[-self._DEDUP_MAX_HISTORY :]
            self._recent_prompt_hashes[agent_id] = history
            return False

    # ── Command Rate Limiting ─────────────────────────────────────────

    _RATE_LIMIT_WINDOW_SECONDS = 10.0
    _RATE_LIMIT_MAX_COMMANDS = 5

    def is_command_rate_limited(self, agent_id: int) -> bool:
        now = time.time()

        if self._redis_available():
            try:
                key = self._rkey("cmd_rate", agent_id)
                raw = self._redis.get(key)
                times = json.loads(raw) if raw else []
                times = [
                    t for t in times if (now - t) < self._RATE_LIMIT_WINDOW_SECONDS
                ]
                self._redis.set(
                    key, json.dumps(times), ex=int(self._RATE_LIMIT_WINDOW_SECONDS * 2)
                )
                with self._lock:
                    self._command_creation_times[agent_id] = times
                return len(times) >= self._RATE_LIMIT_MAX_COMMANDS
            except Exception:
                pass

        with self._lock:
            times = self._command_creation_times.get(agent_id, [])
            times = [t for t in times if (now - t) < self._RATE_LIMIT_WINDOW_SECONDS]
            self._command_creation_times[agent_id] = times
            return len(times) >= self._RATE_LIMIT_MAX_COMMANDS

    def record_command_creation(self, agent_id: int) -> None:
        now = time.time()

        if self._redis_available():
            try:
                key = self._rkey("cmd_rate", agent_id)
                raw = self._redis.get(key)
                times = json.loads(raw) if raw else []
                times = [
                    t for t in times if (now - t) < self._RATE_LIMIT_WINDOW_SECONDS
                ]
                times.append(now)
                self._redis.set(
                    key, json.dumps(times), ex=int(self._RATE_LIMIT_WINDOW_SECONDS * 2)
                )
            except Exception:
                pass

        with self._lock:
            times = self._command_creation_times.get(agent_id, [])
            times = [t for t in times if (now - t) < self._RATE_LIMIT_WINDOW_SECONDS]
            times.append(now)
            self._command_creation_times[agent_id] = times

    # ── Lifecycle (bulk operations) ──────────────────────────────────

    def on_session_start(self, agent_id: int) -> None:
        """Clear session-scoped state for a new session."""
        if self._redis_available():
            try:
                self._redis.delete(
                    self._rkey("transcript_pos", agent_id),
                    self._rkey("progress_texts", agent_id),
                )
            except Exception:
                pass
        with self._lock:
            self._transcript_positions.pop(agent_id, None)
            self._progress_texts.pop(agent_id, None)

    def on_session_end(self, agent_id: int) -> None:
        """Clear all per-agent state when a session ends."""
        if self._redis_available():
            try:
                self._redis.delete(
                    self._rkey("awaiting_tool", agent_id),
                    self._rkey("respond_inflight", agent_id),
                    self._rkey("transcript_pos", agent_id),
                    self._rkey("progress_texts", agent_id),
                    self._rkey_set("skill_inject", agent_id),
                    self._rkey("prompt_hashes", agent_id),
                    self._rkey("cmd_rate", agent_id),
                )
            except Exception:
                pass
        with self._lock:
            self._awaiting_tool.pop(agent_id, None)
            self._respond_inflight.pop(agent_id, None)
            self._transcript_positions.pop(agent_id, None)
            self._progress_texts.pop(agent_id, None)
            self._skill_injection_pending.discard(agent_id)
            self._recent_prompt_hashes.pop(agent_id, None)
            self._command_creation_times.pop(agent_id, None)

    def on_new_response_cycle(self, agent_id: int) -> None:
        """Clear state for a new user->agent response cycle."""
        if self._redis_available():
            try:
                self._redis.delete(
                    self._rkey("awaiting_tool", agent_id),
                    self._rkey("progress_texts", agent_id),
                )
            except Exception:
                pass
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


# ── Module-level singleton ───────────────────────────────────────────

_instance: AgentHookState | None = None
_instance_lock = threading.Lock()


def get_agent_hook_state(redis_manager=None) -> AgentHookState:
    """Get or create the global AgentHookState singleton."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = AgentHookState(redis_manager=redis_manager)
    return _instance


def configure_agent_hook_state(redis_manager=None) -> AgentHookState:
    """Configure (or reconfigure) the global AgentHookState singleton with redis_manager."""
    global _instance
    with _instance_lock:
        _instance = AgentHookState(redis_manager=redis_manager)
    return _instance


def reset_agent_hook_state() -> None:
    """Reset the global singleton. For testing only."""
    global _instance
    with _instance_lock:
        if _instance is not None:
            _instance.reset()
        _instance = AgentHookState()
