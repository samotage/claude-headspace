"""Hook receiver types, constants, and receiver state management.

Extracted from hook_receiver.py for modularity.
"""

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import NamedTuple

logger = logging.getLogger(__name__)


# --- Constants ---

# Tools where post_tool_use should NOT resume from AWAITING_INPUT
# because user interaction happens AFTER the tool completes.
# NOTE: AskUserQuestion is intentionally excluded — its post_tool_use
# fires AFTER the user answers the dialog, so we should resume to PROCESSING.
# ExitPlanMode is different: post_tool_use fires after the plan is shown
# but BEFORE the user approves/rejects (approval comes as a new user prompt).
USER_INTERACTIVE_TOOLS = {"ExitPlanMode"}

# Tools where pre_tool_use should transition to AWAITING_INPUT
# (user interaction happens AFTER the tool completes, not via permission_request)
PRE_TOOL_USE_INTERACTIVE = {"AskUserQuestion", "ExitPlanMode"}

# Don't infer a new command from post_tool_use if the previous command
# completed less than this many seconds ago (tail-end tool activity).
INFERRED_COMMAND_COOLDOWN_SECONDS = 30


# --- Data types ---


class HookEventType(str, Enum):
    SESSION_START = "session_start"
    SESSION_END = "session_end"
    USER_PROMPT_SUBMIT = "user_prompt_submit"
    STOP = "stop"
    NOTIFICATION = "notification"
    POST_TOOL_USE = "post_tool_use"
    PRE_TOOL_USE = "pre_tool_use"
    PERMISSION_REQUEST = "permission_request"


class HookMode(str, Enum):
    HOOKS_ACTIVE = "hooks_active"
    POLLING_FALLBACK = "polling_fallback"


class HookEventResult(NamedTuple):
    success: bool
    agent_id: int | None = None
    state_changed: bool = False
    new_state: str | None = None
    error_message: str | None = None


# --- Receiver state ---


@dataclass
class HookReceiverState:
    enabled: bool = True
    last_event_at: datetime | None = None
    last_event_type: HookEventType | None = None
    mode: HookMode = HookMode.POLLING_FALLBACK
    events_received: int = 0
    polling_interval_with_hooks: int = 60
    polling_interval_fallback: int = 2
    fallback_timeout: int = 300
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def record_event(self, event_type: HookEventType) -> None:
        with self._lock:
            self.last_event_at = datetime.now(timezone.utc)
            self.last_event_type = event_type
            self.events_received += 1
            if self.mode == HookMode.POLLING_FALLBACK:
                self.mode = HookMode.HOOKS_ACTIVE
                logger.info("Hook receiver mode changed to HOOKS_ACTIVE")

    def check_fallback(self) -> None:
        with self._lock:
            if self.mode != HookMode.HOOKS_ACTIVE or self.last_event_at is None:
                return
            elapsed = (datetime.now(timezone.utc) - self.last_event_at).total_seconds()
            if elapsed > self.fallback_timeout:
                self.mode = HookMode.POLLING_FALLBACK
                logger.warning(
                    f"No hook events for {elapsed:.0f}s, reverting to POLLING_FALLBACK"
                )

    def get_polling_interval(self) -> int:
        with self._lock:
            return (
                self.polling_interval_with_hooks
                if self.mode == HookMode.HOOKS_ACTIVE
                else self.polling_interval_fallback
            )


_receiver_state = HookReceiverState()


def get_receiver_state() -> HookReceiverState:
    return _receiver_state


def configure_receiver(
    enabled: bool | None = None,
    polling_interval_with_hooks: int | None = None,
    fallback_timeout: int | None = None,
) -> None:
    state = get_receiver_state()
    with state._lock:
        if enabled is not None:
            state.enabled = enabled
        if polling_interval_with_hooks is not None:
            state.polling_interval_with_hooks = polling_interval_with_hooks
        if fallback_timeout is not None:
            state.fallback_timeout = fallback_timeout


def reset_receiver_state() -> None:
    global _receiver_state
    from .hook_agent_state import get_agent_hook_state

    _receiver_state = HookReceiverState()
    get_agent_hook_state().reset()
