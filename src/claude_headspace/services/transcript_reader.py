"""Transcript reader utility for extracting content from Claude Code .jsonl files.

Reads transcript files produced by Claude Code sessions and extracts
the agent's last response text for populating turn content.
"""

import json
import logging
import os
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

# Default maximum length for extracted transcript content
DEFAULT_MAX_CONTENT_LENGTH = 10000


@dataclass
class TranscriptEntry:
    """A single entry from a Claude Code transcript .jsonl file."""

    type: str
    role: str | None = None
    content: str | None = None
    raw: dict | None = None


@dataclass
class TranscriptReadResult:
    """Result of reading a transcript file."""

    success: bool
    text: str = ""
    error: str | None = None
    entries_read: int = 0


def read_transcript_file(
    transcript_path: str,
    max_content_length: int = DEFAULT_MAX_CONTENT_LENGTH,
) -> TranscriptReadResult:
    """
    Read a Claude Code transcript .jsonl file and extract the last agent response.

    The transcript file contains JSON lines with various entry types.
    We look for the last assistant message to extract the agent's response text.

    Args:
        transcript_path: Absolute path to the .jsonl transcript file
        max_content_length: Maximum length of extracted text (truncated if longer)

    Returns:
        TranscriptReadResult with the extracted text or error information
    """
    if not transcript_path:
        return TranscriptReadResult(
            success=False,
            error="No transcript path provided",
        )

    if not os.path.exists(transcript_path):
        logger.warning(f"Transcript file not found: {transcript_path}")
        return TranscriptReadResult(
            success=False,
            error=f"Transcript file not found: {transcript_path}",
        )

    try:
        entries = _parse_jsonl_file(transcript_path)
        if not entries:
            return TranscriptReadResult(
                success=True,
                text="",
                entries_read=0,
            )

        # Find the last assistant response
        last_response = _extract_last_agent_response(entries)
        if not last_response:
            return TranscriptReadResult(
                success=True,
                text="",
                entries_read=len(entries),
            )

        # Truncate if needed
        text = last_response
        if len(text) > max_content_length:
            text = text[:max_content_length] + "... [truncated]"

        return TranscriptReadResult(
            success=True,
            text=text,
            entries_read=len(entries),
        )

    except PermissionError:
        logger.warning(f"Permission denied reading transcript: {transcript_path}")
        return TranscriptReadResult(
            success=False,
            error=f"Permission denied: {transcript_path}",
        )
    except Exception as e:
        logger.warning(f"Error reading transcript {transcript_path}: {e}")
        return TranscriptReadResult(
            success=False,
            error=str(e),
        )


def read_new_entries_from_position(
    transcript_path: str,
    position: int = 0,
) -> tuple[list[TranscriptEntry], int]:
    """
    Read new entries from a transcript file starting at a byte position.

    Used for incremental reading by the file watcher.

    Args:
        transcript_path: Path to the .jsonl transcript file
        position: Byte position to start reading from

    Returns:
        Tuple of (new_entries, new_position)
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
                entry = _parse_entry(data)
                if entry:
                    entries.append(entry)
            except json.JSONDecodeError:
                continue

        return entries, new_position

    except Exception as e:
        logger.warning(f"Error reading transcript incrementally: {e}")
        return [], position


def _parse_jsonl_file(path: str) -> list[TranscriptEntry]:
    """Parse a .jsonl file into transcript entries."""
    entries = []
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                entry = _parse_entry(data)
                if entry:
                    entries.append(entry)
            except json.JSONDecodeError:
                continue
    return entries


def _parse_entry(data: dict) -> Optional[TranscriptEntry]:
    """Parse a JSON object into a TranscriptEntry."""
    if not isinstance(data, dict):
        return None

    entry_type = data.get("type", "")
    role = data.get("role")

    # Extract content — Claude Code uses various formats
    content = None
    if "content" in data:
        raw_content = data["content"]
        if isinstance(raw_content, str):
            content = raw_content
        elif isinstance(raw_content, list):
            # Content blocks: [{"type": "text", "text": "..."}, ...]
            text_parts = []
            for block in raw_content:
                if isinstance(block, dict) and block.get("type") == "text":
                    text_parts.append(block.get("text", ""))
            content = "\n".join(text_parts) if text_parts else None
    elif "message" in data:
        content = data.get("message")

    return TranscriptEntry(
        type=entry_type,
        role=role,
        content=content,
        raw=data,
    )


def _extract_last_agent_response(entries: list[TranscriptEntry]) -> Optional[str]:
    """Extract the text of the last assistant/agent response from transcript entries."""
    # Walk backwards to find the last assistant message
    for entry in reversed(entries):
        if entry.role == "assistant" and entry.content:
            return entry.content
    return None
