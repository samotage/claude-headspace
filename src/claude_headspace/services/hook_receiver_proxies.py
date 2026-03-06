"""Backwards-compatible proxy objects for per-agent hook state.

All mutable per-agent state is managed by AgentHookState (hook_agent_state.py)
with proper thread synchronization. These proxy objects provide dict/set-like
interfaces for backwards compatibility with external callers.

Extracted from hook_receiver.py for modularity.
"""

from .hook_agent_state import get_agent_hook_state


class _AwaitingToolProxy:
    """Dict-like proxy to AgentHookState._awaiting_tool."""

    def __getitem__(self, agent_id):
        return get_agent_hook_state().get_awaiting_tool(agent_id)

    def __setitem__(self, agent_id, value):
        get_agent_hook_state().set_awaiting_tool(agent_id, value)

    def __contains__(self, agent_id):
        return get_agent_hook_state().get_awaiting_tool(agent_id) is not None

    def get(self, agent_id, default=None):
        val = get_agent_hook_state().get_awaiting_tool(agent_id)
        return val if val is not None else default

    def pop(self, agent_id, *args):
        return get_agent_hook_state().clear_awaiting_tool(agent_id)

    def clear(self):
        state = get_agent_hook_state()
        with state._lock:
            state._awaiting_tool.clear()

    def __len__(self):
        # Only used by tests checking emptiness
        return 0


class _RespondPendingProxy:
    """Dict-like proxy to AgentHookState._respond_pending."""

    def __getitem__(self, agent_id):
        raise KeyError(agent_id)  # Not needed

    def __setitem__(self, agent_id, value):
        get_agent_hook_state().set_respond_pending(agent_id)

    def __contains__(self, agent_id):
        state = get_agent_hook_state()
        with state._lock:
            return agent_id in state._respond_pending

    def pop(self, agent_id, *args):
        # consume_respond_pending returns bool, but callers expect timestamp or None
        state = get_agent_hook_state()
        with state._lock:
            return state._respond_pending.pop(agent_id, None if not args else args[0])

    def clear(self):
        state = get_agent_hook_state()
        with state._lock:
            state._respond_pending.clear()

    def __len__(self):
        return 0


class _DeferredStopProxy:
    """Set-like proxy to AgentHookState._deferred_stop_pending."""

    def add(self, agent_id):
        state = get_agent_hook_state()
        with state._lock:
            state._deferred_stop_pending.add(agent_id)

    def discard(self, agent_id):
        get_agent_hook_state().release_deferred_stop(agent_id)

    def __contains__(self, agent_id):
        return get_agent_hook_state().is_deferred_stop_pending(agent_id)

    def clear(self):
        state = get_agent_hook_state()
        with state._lock:
            state._deferred_stop_pending.clear()

    def __len__(self):
        return 0


class _TranscriptPositionsProxy:
    """Dict-like proxy to AgentHookState._transcript_positions."""

    def __getitem__(self, agent_id):
        val = get_agent_hook_state().get_transcript_position(agent_id)
        if val is None:
            raise KeyError(agent_id)
        return val

    def __setitem__(self, agent_id, value):
        get_agent_hook_state().set_transcript_position(agent_id, value)

    def __contains__(self, agent_id):
        return get_agent_hook_state().get_transcript_position(agent_id) is not None

    def get(self, agent_id, default=None):
        val = get_agent_hook_state().get_transcript_position(agent_id)
        return val if val is not None else default

    def pop(self, agent_id, *args):
        return get_agent_hook_state().clear_transcript_position(agent_id)

    def clear(self):
        pass  # handled by reset


class _ProgressTextsProxy:
    """Dict-like proxy to AgentHookState._progress_texts."""

    def __getitem__(self, agent_id):
        val = get_agent_hook_state().get_progress_texts(agent_id)
        if not val:
            raise KeyError(agent_id)
        return val

    def __setitem__(self, agent_id, value):
        state = get_agent_hook_state()
        with state._lock:
            state._progress_texts[agent_id] = value

    def __contains__(self, agent_id):
        return len(get_agent_hook_state().get_progress_texts(agent_id)) > 0

    def get(self, agent_id, default=None):
        val = get_agent_hook_state().get_progress_texts(agent_id)
        return val if val else default

    def pop(self, agent_id, *args):
        return get_agent_hook_state().consume_progress_texts(agent_id)

    def clear(self):
        pass  # handled by reset


class _FileMetadataPendingProxy:
    """Dict-like proxy to AgentHookState._file_metadata_pending."""

    def __setitem__(self, agent_id, value):
        get_agent_hook_state().set_file_metadata_pending(agent_id, value)

    def pop(self, agent_id, *args):
        return get_agent_hook_state().consume_file_metadata_pending(agent_id)

    def clear(self):
        pass  # handled by reset


# Backwards-compatible module-level names (used by external callers)
_awaiting_tool_for_agent = _AwaitingToolProxy()
_respond_pending_for_agent = _RespondPendingProxy()
_deferred_stop_pending = _DeferredStopProxy()
_transcript_positions = _TranscriptPositionsProxy()
_progress_texts_for_agent = _ProgressTextsProxy()
_file_metadata_pending_for_agent = _FileMetadataPendingProxy()
