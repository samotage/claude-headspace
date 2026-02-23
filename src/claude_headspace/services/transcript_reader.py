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
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

MAX_CONTENT_LENGTH = 10000


@dataclass
class TranscriptEntry:
    """A parsed transcript entry."""

    type: str
    role: str | None = None
    content: str | None = None
    timestamp: datetime | None = None
    raw_data: dict | None = None


@dataclass
class TranscriptReadResult:
    """Result of reading a transcript file."""

    success: bool
    text: str = ""
    error: str | None = None
    timestamp: datetime | None = None


def _parse_jsonl_timestamp(data: dict) -> datetime | None:
    """Parse a timestamp from a JSONL entry.

    JSONL entries may have a "timestamp" field as an ISO string or unix epoch.
    Returns a timezone-aware datetime or None if parsing fails.
    """
    ts_raw = data.get("timestamp")
    if not ts_raw:
        return None
    try:
        if isinstance(ts_raw, str):
            if ts_raw.endswith("Z"):
                ts_raw = ts_raw[:-1] + "+00:00"
            ts = datetime.fromisoformat(ts_raw)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            return ts
        elif isinstance(ts_raw, (int, float)):
            return datetime.fromtimestamp(ts_raw, tz=timezone.utc)
    except (ValueError, OSError):
        pass
    return None


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
        # Reverse-read strategy: only read the last 64KB instead of the whole file
        _TAIL_SIZE = 64 * 1024
        file_size = os.path.getsize(transcript_path)
        # errors="replace" handles seeking into the middle of a multi-byte
        # UTF-8 sequence — replacement chars land in the partial line that
        # readline() discards, so actual content is unaffected.
        with open(transcript_path, "r", errors="replace") as f:
            start_pos = max(0, file_size - _TAIL_SIZE)
            if start_pos > 0:
                f.seek(start_pos)
                f.readline()  # Skip partial line at seek boundary
            lines = f.readlines()

        # Walk backwards, collecting assistant texts until we hit a user message
        parts: list[str] = []
        result_timestamp: datetime | None = None
        logger.debug(f"TRANSCRIPT_READ: walking backwards through {len(lines)} lines from {transcript_path}")
        lines_scanned = 0
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
            lines_scanned += 1

            # User message with content marks the start of the current turn — stop collecting.
            # Only skip user entries with NO content at all (truly empty turn boundary
            # markers). User entries with string content (prompts), tool_result blocks,
            # or any other content are real turn boundaries.
            if entry_type == "user":
                msg = data.get("message", {})
                content = msg.get("content") if isinstance(msg, dict) else None
                has_content = bool(
                    (isinstance(content, str) and content.strip())
                    or (isinstance(content, list) and len(content) > 0)
                )
                if has_content:
                    logger.debug(f"TRANSCRIPT_READ: hit user entry with content after scanning {lines_scanned} lines, collected {len(parts)} parts")
                    break
                logger.debug(f"TRANSCRIPT_READ: skipping empty user entry at scan line {lines_scanned}")
                continue

            if entry_type != "assistant":
                continue

            _role, text = _extract_text(data)
            if text:
                parts.append(text)
                # Capture timestamp from the most recent (first found) assistant entry
                if result_timestamp is None:
                    result_timestamp = _parse_jsonl_timestamp(data)
                logger.debug(f"TRANSCRIPT_READ: collected assistant text ({len(text)} chars): {repr(text[:100])}")

        if not parts:
            logger.debug(f"TRANSCRIPT_READ: no assistant text found after scanning {lines_scanned} lines")
            return TranscriptReadResult(success=True, text="")

        # Reverse to restore chronological order
        parts.reverse()
        combined = "\n\n".join(parts)

        if len(combined) > MAX_CONTENT_LENGTH:
            combined = combined[:MAX_CONTENT_LENGTH] + "... [truncated]"

        return TranscriptReadResult(success=True, text=combined, timestamp=result_timestamp)

    except Exception as e:
        logger.warning(f"Error reading transcript {transcript_path}: {e}")
        return TranscriptReadResult(success=False, error=str(e))


def read_last_user_message(transcript_path: str) -> TranscriptReadResult:
    """Read the most recent user message text from a transcript .jsonl file.

    Walks backwards from the end of the file looking for the first ``user``
    entry with text content.  Returns the text of that entry.  Used as a
    fallback to recover user command text when hooks arrive out of order.
    """
    if not transcript_path:
        return TranscriptReadResult(success=False, error="No transcript path")

    if not os.path.exists(transcript_path):
        return TranscriptReadResult(success=False, error=f"File not found: {transcript_path}")

    try:
        _TAIL_SIZE = 64 * 1024
        file_size = os.path.getsize(transcript_path)
        with open(transcript_path, "r", errors="replace") as f:
            start_pos = max(0, file_size - _TAIL_SIZE)
            if start_pos > 0:
                f.seek(start_pos)
                f.readline()  # Skip partial line at seek boundary
            lines = f.readlines()

        for line in reversed(lines):
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue

            if data.get("type") != "user":
                continue

            msg = data.get("message", {})
            if not isinstance(msg, dict):
                continue

            content = msg.get("content")
            # Extract text from string content
            if isinstance(content, str) and content.strip():
                text = content.strip()
                if len(text) > MAX_CONTENT_LENGTH:
                    text = text[:MAX_CONTENT_LENGTH] + "... [truncated]"
                return TranscriptReadResult(success=True, text=text)

            # Extract text from content blocks
            if isinstance(content, list):
                parts = []
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        t = block.get("text", "")
                        if t.strip():
                            parts.append(t.strip())
                if parts:
                    text = "\n".join(parts)
                    if len(text) > MAX_CONTENT_LENGTH:
                        text = text[:MAX_CONTENT_LENGTH] + "... [truncated]"
                    return TranscriptReadResult(success=True, text=text)

        return TranscriptReadResult(success=True, text="")

    except Exception as e:
        logger.warning(f"Error reading last user message from {transcript_path}: {e}")
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
        with open(transcript_path, "r", errors="replace") as f:
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
            ts = _parse_jsonl_timestamp(data)
            entries.append(TranscriptEntry(
                type=data.get("type", ""),
                role=role,
                content=text,
                timestamp=ts,
                raw_data=data,
            ))

        return entries, new_position

    except Exception as e:
        logger.warning(f"Error reading transcript incrementally: {e}")
        return [], position
