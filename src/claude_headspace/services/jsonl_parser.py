"""JSONL parser for Claude Code session files."""

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class ParsedTurn:
    """Data class representing a parsed turn from Claude Code jsonl."""

    actor: str  # "user" or "assistant"
    text: str
    timestamp: datetime
    raw_data: dict  # Original JSON for extensibility
    message_type: str  # Original type field from jsonl


class JSONLParser:
    """
    Incremental parser for Claude Code jsonl files.

    Tracks file position to only process new lines since last read.
    """

    def __init__(self, file_path: str) -> None:
        """
        Initialize the parser.

        Args:
            file_path: Path to the jsonl file to parse
        """
        self._file_path = file_path
        self._position = 0

    @property
    def file_path(self) -> str:
        """Get the file path."""
        return self._file_path

    @property
    def current_position(self) -> int:
        """Get current byte position in file."""
        return self._position

    def reset_position(self) -> None:
        """Reset to beginning of file."""
        self._position = 0

    def read_new_lines(self) -> list[ParsedTurn]:
        """
        Read and parse lines added since last read.

        Returns:
            List of parsed turns (only user and assistant messages)
        """
        turns = []

        try:
            with open(self._file_path, "r", encoding="utf-8") as f:
                # Seek to last known position
                f.seek(self._position)

                for line in f:
                    parsed = self._parse_line(line)
                    if parsed:
                        turns.append(parsed)

                # Update position to end of file
                self._position = f.tell()

        except FileNotFoundError:
            logger.warning(f"JSONL file not found: {self._file_path}")
        except PermissionError:
            logger.warning(f"Permission denied reading: {self._file_path}")
        except Exception as e:
            logger.error(f"Error reading JSONL file: {e}")

        return turns

    def _parse_line(self, line: str) -> Optional[ParsedTurn]:
        """
        Parse a single jsonl line.

        Args:
            line: Raw line from jsonl file

        Returns:
            ParsedTurn if line is a user/assistant message, None otherwise
        """
        line = line.strip()
        if not line:
            return None

        try:
            data = json.loads(line)
        except json.JSONDecodeError as e:
            logger.warning(f"Malformed JSON line: {e}")
            return None

        # Only process user and assistant messages
        msg_type = data.get("type")
        if msg_type not in ("user", "assistant"):
            return None

        # Extract text content
        text = self._extract_text(data)
        if text is None:
            return None

        # Parse timestamp
        timestamp = self._parse_timestamp(data.get("timestamp"))

        # Determine actor
        actor = "user" if msg_type == "user" else "assistant"

        return ParsedTurn(
            actor=actor,
            text=text,
            timestamp=timestamp,
            raw_data=data,
            message_type=msg_type,
        )

    def _extract_text(self, data: dict) -> Optional[str]:
        """
        Extract text content from a message.

        Claude Code jsonl has different structures for user vs assistant:
        - user: {"type": "user", "message": {"role": "user", "content": "..."}}
        - assistant: {"type": "assistant", "message": {"content": [{"type": "text", "text": "..."}]}}

        Args:
            data: Parsed JSON data

        Returns:
            Text content, or None if not extractable
        """
        message = data.get("message", {})

        # Handle content as string (user messages)
        content = message.get("content")
        if isinstance(content, str):
            return content

        # Handle content as list (assistant messages)
        if isinstance(content, list):
            text_parts = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    text_parts.append(item.get("text", ""))
            return "\n".join(text_parts) if text_parts else None

        return None

    def _parse_timestamp(self, timestamp_str: Optional[str]) -> datetime:
        """
        Parse ISO 8601 timestamp string.

        Args:
            timestamp_str: ISO 8601 timestamp string

        Returns:
            datetime object (UTC)
        """
        if not timestamp_str:
            return datetime.utcnow()

        try:
            # Handle Z suffix
            if timestamp_str.endswith("Z"):
                timestamp_str = timestamp_str[:-1] + "+00:00"
            return datetime.fromisoformat(timestamp_str)
        except ValueError:
            logger.warning(f"Invalid timestamp format: {timestamp_str}")
            return datetime.utcnow()
