"""Hook receiver service for Claude Code lifecycle events.

This module is a thin facade that re-exports all public symbols from the
modularized hook receiver submodules. All consumers can continue importing
from `hook_receiver` without changes.

Submodules:
- hook_receiver_types: enums, namedtuples, receiver state management
- hook_receiver_helpers: shared helper functions (broadcast, notifications, etc.)
- hook_handler_session_start: process_session_start
- hook_handler_session_end: process_session_end
- hook_handler_user_prompt: process_user_prompt_submit
- hook_handler_stop: process_stop
- hook_handler_awaiting_input: process_notification, process_pre_tool_use, process_permission_request
- hook_handler_post_tool_use: process_post_tool_use
"""

# --- Types & constants ---
# --- Aliased extractors (re-exported for backwards compatibility) ---
from .hook_extractors import (  # noqa: F401
    extract_question_text as _extract_question_text,
)

# --- Hook processors ---
from .hook_handler_awaiting_input import (  # noqa: F401
    _handle_awaiting_input,
    process_notification,
    process_permission_request,
    process_pre_tool_use,
)
from .hook_handler_post_tool_use import process_post_tool_use  # noqa: F401
from .hook_handler_session_end import process_session_end  # noqa: F401
from .hook_handler_session_start import process_session_start  # noqa: F401
from .hook_handler_stop import process_stop  # noqa: F401
from .hook_handler_user_prompt import process_user_prompt_submit  # noqa: F401

# --- Helpers (used by handlers and by hook_deferred_stop) ---
from .hook_receiver_helpers import (  # noqa: F401
    _broadcast_state_change,
    _broadcast_turn_created,
    _capture_progress_text,
    _capture_progress_text_impl,
    _execute_pending_summarisations,
    _extract_transcript_content,
    _get_lifecycle_manager,
    _schedule_deferred_stop,
    _send_completion_notification,
    _send_notification,
    _trigger_priority_scoring,
    broadcast_card_refresh,
    detect_agent_intent,
)
from .hook_receiver_types import (  # noqa: F401
    INFERRED_COMMAND_COOLDOWN_SECONDS,
    PRE_TOOL_USE_INTERACTIVE,
    USER_INTERACTIVE_TOOLS,
    HookEventResult,
    HookEventType,
    HookMode,
    HookReceiverState,
    configure_receiver,
    get_receiver_state,
    reset_receiver_state,
)
