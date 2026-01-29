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
]
