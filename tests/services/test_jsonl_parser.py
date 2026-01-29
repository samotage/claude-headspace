"""Tests for JSONL parser."""

import json
import os
import tempfile
from datetime import datetime, timezone

import pytest

from claude_headspace.services.jsonl_parser import JSONLParser, ParsedTurn


class TestParsedTurn:
    """Test ParsedTurn dataclass."""

    def test_create_turn(self):
        """Test creating a parsed turn."""
        turn = ParsedTurn(
            actor="user",
            text="Hello",
            timestamp=datetime.now(timezone.utc),
            raw_data={"type": "user"},
            message_type="user",
        )
        assert turn.actor == "user"
        assert turn.text == "Hello"
        assert turn.message_type == "user"


class TestJSONLParser:
    """Test JSONLParser class."""

    @pytest.fixture
    def temp_jsonl(self):
        """Create a temporary jsonl file."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False
        ) as f:
            yield f.name
        os.unlink(f.name)

    def test_parser_creation(self, temp_jsonl):
        """Test creating a parser."""
        parser = JSONLParser(temp_jsonl)
        assert parser.file_path == temp_jsonl
        assert parser.current_position == 0

    def test_read_empty_file(self, temp_jsonl):
        """Test reading empty file."""
        parser = JSONLParser(temp_jsonl)
        turns = parser.read_new_lines()
        assert turns == []

    def test_read_user_message(self, temp_jsonl):
        """Test reading user message."""
        user_msg = {
            "type": "user",
            "message": {"role": "user", "content": "Hello, Claude!"},
            "timestamp": "2026-01-29T10:00:00Z",
        }
        with open(temp_jsonl, "w") as f:
            f.write(json.dumps(user_msg) + "\n")

        parser = JSONLParser(temp_jsonl)
        turns = parser.read_new_lines()

        assert len(turns) == 1
        assert turns[0].actor == "user"
        assert turns[0].text == "Hello, Claude!"

    def test_read_assistant_message(self, temp_jsonl):
        """Test reading assistant message."""
        assistant_msg = {
            "type": "assistant",
            "message": {
                "role": "assistant",
                "content": [{"type": "text", "text": "Hello! How can I help?"}],
            },
            "timestamp": "2026-01-29T10:00:01Z",
        }
        with open(temp_jsonl, "w") as f:
            f.write(json.dumps(assistant_msg) + "\n")

        parser = JSONLParser(temp_jsonl)
        turns = parser.read_new_lines()

        assert len(turns) == 1
        assert turns[0].actor == "assistant"
        assert turns[0].text == "Hello! How can I help?"

    def test_read_multiple_text_blocks(self, temp_jsonl):
        """Test reading assistant message with multiple text blocks."""
        assistant_msg = {
            "type": "assistant",
            "message": {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "First part."},
                    {"type": "text", "text": "Second part."},
                ],
            },
            "timestamp": "2026-01-29T10:00:01Z",
        }
        with open(temp_jsonl, "w") as f:
            f.write(json.dumps(assistant_msg) + "\n")

        parser = JSONLParser(temp_jsonl)
        turns = parser.read_new_lines()

        assert len(turns) == 1
        assert "First part." in turns[0].text
        assert "Second part." in turns[0].text

    def test_skip_non_message_types(self, temp_jsonl):
        """Test that non-user/assistant messages are skipped."""
        lines = [
            {"type": "progress", "data": {}},
            {"type": "user", "message": {"content": "Hi"}, "timestamp": "2026-01-29T10:00:00Z"},
            {"type": "file-history-snapshot", "snapshot": {}},
        ]
        with open(temp_jsonl, "w") as f:
            for line in lines:
                f.write(json.dumps(line) + "\n")

        parser = JSONLParser(temp_jsonl)
        turns = parser.read_new_lines()

        assert len(turns) == 1
        assert turns[0].actor == "user"

    def test_handle_malformed_line(self, temp_jsonl):
        """Test handling malformed JSON line."""
        with open(temp_jsonl, "w") as f:
            f.write("not valid json\n")
            f.write(json.dumps({
                "type": "user",
                "message": {"content": "Valid message"},
                "timestamp": "2026-01-29T10:00:00Z",
            }) + "\n")

        parser = JSONLParser(temp_jsonl)
        turns = parser.read_new_lines()

        # Should skip malformed line and parse valid one
        assert len(turns) == 1
        assert turns[0].text == "Valid message"

    def test_incremental_reading(self, temp_jsonl):
        """Test incremental reading of file."""
        # Write first message
        with open(temp_jsonl, "w") as f:
            f.write(json.dumps({
                "type": "user",
                "message": {"content": "First"},
                "timestamp": "2026-01-29T10:00:00Z",
            }) + "\n")

        parser = JSONLParser(temp_jsonl)
        turns1 = parser.read_new_lines()
        assert len(turns1) == 1
        assert turns1[0].text == "First"

        # Append second message
        with open(temp_jsonl, "a") as f:
            f.write(json.dumps({
                "type": "user",
                "message": {"content": "Second"},
                "timestamp": "2026-01-29T10:00:01Z",
            }) + "\n")

        turns2 = parser.read_new_lines()
        assert len(turns2) == 1
        assert turns2[0].text == "Second"

    def test_reset_position(self, temp_jsonl):
        """Test resetting file position."""
        with open(temp_jsonl, "w") as f:
            f.write(json.dumps({
                "type": "user",
                "message": {"content": "Message"},
                "timestamp": "2026-01-29T10:00:00Z",
            }) + "\n")

        parser = JSONLParser(temp_jsonl)
        turns1 = parser.read_new_lines()
        assert len(turns1) == 1

        # Reset and read again
        parser.reset_position()
        turns2 = parser.read_new_lines()
        assert len(turns2) == 1

    def test_nonexistent_file(self):
        """Test handling nonexistent file."""
        parser = JSONLParser("/nonexistent/file.jsonl")
        turns = parser.read_new_lines()
        assert turns == []

    def test_parse_timestamp_with_z_suffix(self, temp_jsonl):
        """Test parsing timestamp with Z suffix."""
        with open(temp_jsonl, "w") as f:
            f.write(json.dumps({
                "type": "user",
                "message": {"content": "Test"},
                "timestamp": "2026-01-29T10:00:00Z",
            }) + "\n")

        parser = JSONLParser(temp_jsonl)
        turns = parser.read_new_lines()

        assert turns[0].timestamp.year == 2026
        assert turns[0].timestamp.month == 1
        assert turns[0].timestamp.day == 29

    def test_parse_timestamp_with_offset(self, temp_jsonl):
        """Test parsing timestamp with timezone offset."""
        with open(temp_jsonl, "w") as f:
            f.write(json.dumps({
                "type": "user",
                "message": {"content": "Test"},
                "timestamp": "2026-01-29T10:00:00+11:00",
            }) + "\n")

        parser = JSONLParser(temp_jsonl)
        turns = parser.read_new_lines()

        assert turns[0].timestamp.year == 2026
