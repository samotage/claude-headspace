"""Services package for Claude Headspace."""

from .session_registry import SessionRegistry, RegisteredSession
from .project_decoder import decode_project_path, encode_project_path, locate_jsonl_file
from .jsonl_parser import JSONLParser, ParsedTurn
from .git_metadata import GitMetadata, GitInfo
from .file_watcher import FileWatcher, init_file_watcher

__all__ = [
    "SessionRegistry",
    "RegisteredSession",
    "decode_project_path",
    "encode_project_path",
    "locate_jsonl_file",
    "JSONLParser",
    "ParsedTurn",
    "GitMetadata",
    "GitInfo",
    "FileWatcher",
    "init_file_watcher",
]
