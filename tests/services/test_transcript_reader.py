"""Tests for transcript_reader service."""

import json
import os

import pytest

from claude_headspace.services.transcript_reader import (
    MAX_CONTENT_LENGTH,
    TranscriptReadResult,
    read_transcript_file,
)


def _assistant_line(text: str) -> str:
    """Create a JSONL line for an assistant message."""
    return json.dumps({
        "type": "assistant",
        "message": {
            "role": "assistant",
            "content": [{"type": "text", "text": text}],
        },
    })


def _user_line(text: str) -> str:
    """Create a JSONL line for a user message."""
    return json.dumps({
        "type": "user",
        "message": {
            "role": "user",
            "content": [{"type": "text", "text": text}],
        },
    })


def _progress_line() -> str:
    """Create a JSONL line for a progress event (non-message)."""
    return json.dumps({"type": "progress", "data": "working..."})


class TestReadTranscriptFile:
    """Tests for read_transcript_file()."""

    def test_no_path(self):
        result = read_transcript_file("")
        assert not result.success
        assert "No transcript path" in result.error

    def test_file_not_found(self, tmp_path):
        result = read_transcript_file(str(tmp_path / "missing.jsonl"))
        assert not result.success
        assert "File not found" in result.error

    def test_empty_file(self, tmp_path):
        f = tmp_path / "empty.jsonl"
        f.write_text("")
        result = read_transcript_file(str(f))
        assert result.success
        assert result.text == ""

    def test_single_assistant_message(self, tmp_path):
        f = tmp_path / "single.jsonl"
        f.write_text(_assistant_line("Hello world") + "\n")
        result = read_transcript_file(str(f))
        assert result.success
        assert result.text == "Hello world"

    def test_returns_last_turn_only(self, tmp_path):
        """Assistant messages before the last user message should be excluded."""
        lines = [
            _assistant_line("Old assistant response"),
            _user_line("New user prompt"),
            _assistant_line("New assistant response"),
        ]
        f = tmp_path / "turns.jsonl"
        f.write_text("\n".join(lines) + "\n")
        result = read_transcript_file(str(f))
        assert result.success
        assert result.text == "New assistant response"
        assert "Old assistant" not in result.text

    def test_aggregates_multiple_assistant_messages_in_turn(self, tmp_path):
        """Multiple assistant messages in the same turn should be concatenated."""
        lines = [
            _user_line("Do something complex"),
            _assistant_line("All 17 tests pass. The fix works."),
            _progress_line(),
            _assistant_line("Server is back. The fix strips WERKZEUG vars."),
        ]
        f = tmp_path / "multi.jsonl"
        f.write_text("\n".join(lines) + "\n")
        result = read_transcript_file(str(f))
        assert result.success
        assert "All 17 tests pass" in result.text
        assert "Server is back" in result.text
        # Chronological order: first message comes first
        assert result.text.index("All 17 tests") < result.text.index("Server is back")

    def test_skips_progress_and_other_types(self, tmp_path):
        """Non-assistant, non-user entries should be skipped."""
        lines = [
            _user_line("Go"),
            _progress_line(),
            _assistant_line("Done."),
            _progress_line(),
        ]
        f = tmp_path / "skip.jsonl"
        f.write_text("\n".join(lines) + "\n")
        result = read_transcript_file(str(f))
        assert result.success
        assert result.text == "Done."

    def test_no_assistant_messages(self, tmp_path):
        """File with only user messages should return empty text."""
        f = tmp_path / "noassist.jsonl"
        f.write_text(_user_line("Hello") + "\n")
        result = read_transcript_file(str(f))
        assert result.success
        assert result.text == ""

    def test_truncation(self, tmp_path):
        """Text exceeding MAX_CONTENT_LENGTH should be truncated."""
        long_text = "x" * (MAX_CONTENT_LENGTH + 500)
        f = tmp_path / "long.jsonl"
        f.write_text(_assistant_line(long_text) + "\n")
        result = read_transcript_file(str(f))
        assert result.success
        assert result.text.endswith("... [truncated]")
        assert len(result.text) <= MAX_CONTENT_LENGTH + len("... [truncated]")

    def test_handles_malformed_json_lines(self, tmp_path):
        """Malformed JSON lines should be skipped gracefully."""
        lines = [
            _user_line("Go"),
            "not valid json",
            _assistant_line("Result"),
        ]
        f = tmp_path / "malformed.jsonl"
        f.write_text("\n".join(lines) + "\n")
        result = read_transcript_file(str(f))
        assert result.success
        assert result.text == "Result"

    def test_assistant_with_empty_content(self, tmp_path):
        """Assistant message with no text blocks should be skipped."""
        empty_assistant = json.dumps({
            "type": "assistant",
            "message": {
                "role": "assistant",
                "content": [{"type": "tool_use", "name": "Read"}],
            },
        })
        lines = [
            _user_line("Go"),
            empty_assistant,
            _assistant_line("Actual text"),
        ]
        f = tmp_path / "empty_content.jsonl"
        f.write_text("\n".join(lines) + "\n")
        result = read_transcript_file(str(f))
        assert result.success
        assert result.text == "Actual text"

    def test_multiple_turns_returns_only_latest(self, tmp_path):
        """With multiple user/assistant exchanges, only the last turn is returned."""
        lines = [
            _user_line("First prompt"),
            _assistant_line("First response part 1"),
            _assistant_line("First response part 2"),
            _user_line("Second prompt"),
            _assistant_line("Second response part 1"),
            _assistant_line("Second response part 2"),
        ]
        f = tmp_path / "multi_turn.jsonl"
        f.write_text("\n".join(lines) + "\n")
        result = read_transcript_file(str(f))
        assert result.success
        assert "Second response part 1" in result.text
        assert "Second response part 2" in result.text
        assert "First response" not in result.text
