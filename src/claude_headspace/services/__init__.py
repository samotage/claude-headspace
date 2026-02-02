"""Services package for Claude Headspace."""

from .session_registry import SessionRegistry, RegisteredSession
from .project_decoder import decode_project_path, encode_project_path, locate_jsonl_file
from .jsonl_parser import JSONLParser, ParsedTurn
from .git_metadata import GitMetadata, GitInfo
from .file_watcher import FileWatcher, init_file_watcher
from .event_schemas import (
    EventType,
    PayloadSchema,
    ValidatedEvent,
    validate_event_type,
    validate_payload,
    create_validated_event,
)
from .event_writer import EventWriter, WriteResult, create_event_writer
from .process_monitor import ProcessMonitor, WatcherStatus
from .intent_detector import (
    IntentResult,
    detect_agent_intent,
    detect_user_intent,
    detect_intent,
    QUESTION_PATTERNS,
    COMPLETION_PATTERNS,
    BLOCKED_PATTERNS,
)
from .state_machine import (
    StateMachine,
    TransitionResult,
    validate_transition,
    get_valid_transitions_from,
    is_terminal_state,
    VALID_TRANSITIONS,
)
from .task_lifecycle import TaskLifecycleManager, TurnProcessingResult
from .broadcaster import (
    Broadcaster,
    SSEClient,
    SSEEvent,
    get_broadcaster,
    init_broadcaster,
    shutdown_broadcaster,
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
    # Process monitor
    "ProcessMonitor",
    "WatcherStatus",
    # Intent detector
    "IntentResult",
    "detect_agent_intent",
    "detect_user_intent",
    "detect_intent",
    "QUESTION_PATTERNS",
    "COMPLETION_PATTERNS",
    "BLOCKED_PATTERNS",
    # State machine
    "StateMachine",
    "TransitionResult",
    "validate_transition",
    "get_valid_transitions_from",
    "is_terminal_state",
    "VALID_TRANSITIONS",
    # Task lifecycle
    "TaskLifecycleManager",
    "TurnProcessingResult",
    # Broadcaster
    "Broadcaster",
    "SSEClient",
    "SSEEvent",
    "get_broadcaster",
    "init_broadcaster",
    "shutdown_broadcaster",
]
