"""Services package for Claude Headspace."""

from .broadcaster import (
    Broadcaster,
    SSEClient,
    SSEEvent,
    get_broadcaster,
    init_broadcaster,
    shutdown_broadcaster,
)
from .command_lifecycle import (
    CommandLifecycleManager,
    TurnProcessingResult,
    get_instruction_for_notification,
)
from .event_schemas import (
    EventType,
    PayloadSchema,
    ValidatedEvent,
    create_validated_event,
    validate_event_type,
    validate_payload,
)
from .event_writer import (
    EventWriter,
    WriteResult,
    create_event_writer,
)
from .file_watcher import FileWatcher, init_file_watcher
from .git_metadata import GitInfo, GitMetadata
from .intent_detector import (
    BLOCKED_PATTERNS,
    COMPLETION_PATTERNS,
    QUESTION_PATTERNS,
    IntentResult,
    detect_agent_intent,
    detect_intent,
    detect_user_intent,
)
from .jsonl_parser import JSONLParser, ParsedTurn
from .project_decoder import decode_project_path, encode_project_path, locate_jsonl_file
from .session_registry import RegisteredSession, SessionRegistry
from .state_machine import (
    VALID_TRANSITIONS,
    InvalidTransitionError,
    TransitionResult,
    get_valid_transitions_from,
    is_terminal_state,
    validate_transition,
)

__all__ = [
    # Session registry
    "SessionRegistry",
    "RegisteredSession",
    # Project decoder
    "decode_project_path",
    "encode_project_path",
    "locate_jsonl_file",
    # JSONL parser
    "JSONLParser",
    "ParsedTurn",
    # Git metadata
    "GitMetadata",
    "GitInfo",
    # File watcher
    "FileWatcher",
    "init_file_watcher",
    # Event schemas
    "EventType",
    "PayloadSchema",
    "ValidatedEvent",
    "validate_event_type",
    "validate_payload",
    "create_validated_event",
    # Event writer
    "EventWriter",
    "WriteResult",
    "create_event_writer",
    # Intent detector
    "IntentResult",
    "detect_agent_intent",
    "detect_user_intent",
    "detect_intent",
    "QUESTION_PATTERNS",
    "COMPLETION_PATTERNS",
    "BLOCKED_PATTERNS",
    # State machine
    "InvalidTransitionError",
    "TransitionResult",
    "validate_transition",
    "get_valid_transitions_from",
    "is_terminal_state",
    "VALID_TRANSITIONS",
    # Command lifecycle
    "CommandLifecycleManager",
    "TurnProcessingResult",
    "get_instruction_for_notification",
    # Broadcaster
    "Broadcaster",
    "SSEClient",
    "SSEEvent",
    "get_broadcaster",
    "init_broadcaster",
    "shutdown_broadcaster",
]
