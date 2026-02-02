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
    """Read the last agent response text from a transcript .jsonl file."""
    if not transcript_path:
        return TranscriptReadResult(success=False, error="No transcript path")

    if not os.path.exists(transcript_path):
        return TranscriptReadResult(success=False, error=f"File not found: {transcript_path}")

    try:
        # Read all lines, walk backwards to find the last assistant text
        with open(transcript_path, "r") as f:
            lines = f.readlines()

        for line in reversed(lines):
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue

            if data.get("type") != "assistant":
                continue

            role, text = _extract_text(data)
            if text:
                if len(text) > MAX_CONTENT_LENGTH:
                    text = text[:MAX_CONTENT_LENGTH] + "... [truncated]"
                return TranscriptReadResult(success=True, text=text)

        # No assistant text found
        return TranscriptReadResult(success=True, text="")

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
