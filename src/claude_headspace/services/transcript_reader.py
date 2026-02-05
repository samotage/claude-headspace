"""Read Claude Code .jsonl transcript files and extract agent response text.

JSONL format (one JSON object per line):
  {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": "..."}]}}
  {"type": "user", "message": {"role": "user", "content": [...]}}
  {"type": "progress", ...}
"""

import json
import logging
import os
from dataclasses import dataclass

logger = logging.getLogger(__name__)

MAX_CONTENT_LENGTH = 10000


@dataclass
class TranscriptEntry:
    """A parsed transcript entry."""

    type: str
    role: str | None = None
    content: str | None = None


@dataclass
class TranscriptReadResult:
    """Result of reading a transcript file."""

    success: bool
    text: str = ""
    error: str | None = None


def _extract_text(data: dict) -> tuple[str | None, str | None]:
    """Extract role and text content from a JSONL entry.

    Returns (role, text) — both may be None.
    """
    msg = data.get("message")
    if not isinstance(msg, dict):
        return None, None

    role = msg.get("role")
    content = msg.get("content")
    if not isinstance(content, list):
        return role, None

    parts = []
    for block in content:
        if isinstance(block, dict) and block.get("type") == "text":
            t = block.get("text", "")
            if t.strip():
                parts.append(t)

    return role, "\n".join(parts) if parts else None


def read_transcript_file(transcript_path: str) -> TranscriptReadResult:
    """Read all agent response text from the current turn in a transcript .jsonl file.

    Walks backwards from the end of the file collecting all assistant messages
    until a user message is encountered (marking the turn boundary).  The
    collected texts are returned in chronological order so that completion
    signals from earlier assistant messages in multi-tool-call turns are not
    lost.
    """
    if not transcript_path:
        return TranscriptReadResult(success=False, error="No transcript path")

    if not os.path.exists(transcript_path):
        return TranscriptReadResult(success=False, error=f"File not found: {transcript_path}")

    try:
        with open(transcript_path, "r") as f:
            lines = f.readlines()

        # Walk backwards, collecting assistant texts until we hit a user message
        parts: list[str] = []
        for line in reversed(lines):
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                logger.warning("Malformed JSON line in transcript, skipping")
                continue

            entry_type = data.get("type")

            # User message marks the start of the current turn — stop collecting
            if entry_type == "user":
                break

            if entry_type != "assistant":
                continue

            _role, text = _extract_text(data)
            if text:
                parts.append(text)

        if not parts:
            return TranscriptReadResult(success=True, text="")

        # Reverse to restore chronological order
        parts.reverse()
        combined = "\n\n".join(parts)

        if len(combined) > MAX_CONTENT_LENGTH:
            combined = combined[:MAX_CONTENT_LENGTH] + "... [truncated]"

        return TranscriptReadResult(success=True, text=combined)

    except Exception as e:
        logger.warning(f"Error reading transcript {transcript_path}: {e}")
        return TranscriptReadResult(success=False, error=str(e))


def read_new_entries_from_position(
    transcript_path: str,
    position: int = 0,
) -> tuple[list[TranscriptEntry], int]:
    """Read new entries from a transcript file starting at a byte position.

    Used by the file watcher for incremental reading.
    """
    if not transcript_path or not os.path.exists(transcript_path):
        return [], position

    try:
        with open(transcript_path, "r") as f:
            f.seek(position)
            new_content = f.read()
            new_position = f.tell()

        if not new_content.strip():
            return [], new_position

        entries = []
        for line in new_content.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                logger.warning("Malformed JSON line in transcript, skipping")
                continue

            role, text = _extract_text(data)
            entries.append(TranscriptEntry(
                type=data.get("type", ""),
                role=role,
                content=text,
            ))

        return entries, new_position

    except Exception as e:
        logger.warning(f"Error reading transcript incrementally: {e}")
        return [], position
