"""Tests for project path decoder."""

import os
import tempfile

import pytest

from claude_headspace.services.project_decoder import (
    decode_project_path,
    encode_project_path,
    locate_jsonl_file,
)


class TestDecodeProjectPath:
    """Test decode_project_path function."""

    def test_decode_standard_path(self):
        """Test decoding standard path."""
        folder_name = "-Users-samotage-dev-project"
        expected = "/Users/samotage/dev/project"
        assert decode_project_path(folder_name) == expected

    def test_decode_deep_nested_path(self):
        """Test decoding deeply nested path."""
        folder_name = "-Users-samotage-dev-otagelabs-claude-headspace"
        expected = "/Users/samotage/dev/otagelabs/claude/headspace"
        assert decode_project_path(folder_name) == expected

    def test_decode_empty_string(self):
        """Test decoding empty string."""
        assert decode_project_path("") == ""

    def test_decode_without_leading_dash(self):
        """Test decoding path without leading dash."""
        folder_name = "some-relative-path"
        expected = "some/relative/path"
        assert decode_project_path(folder_name) == expected


class TestEncodeProjectPath:
    """Test encode_project_path function."""

    def test_encode_standard_path(self):
        """Test encoding standard path."""
        path = "/Users/samotage/dev/project"
        expected = "-Users-samotage-dev-project"
        assert encode_project_path(path) == expected

    def test_encode_path_with_trailing_slash(self):
        """Test encoding path with trailing slash."""
        path = "/Users/samotage/dev/project/"
        expected = "-Users-samotage-dev-project"
        assert encode_project_path(path) == expected

    def test_encode_empty_string(self):
        """Test encoding empty string."""
        assert encode_project_path("") == ""

    def test_encode_relative_path(self):
        """Test encoding relative path."""
        path = "relative/path"
        expected = "relative-path"
        assert encode_project_path(path) == expected


class TestRoundTrip:
    """Test encode/decode round trip."""

    def test_round_trip_absolute_path(self):
        """Test encoding then decoding returns original path."""
        original = "/Users/samotage/dev/project"
        encoded = encode_project_path(original)
        decoded = decode_project_path(encoded)
        assert decoded == original

    def test_round_trip_deep_path(self):
        """Test round trip with deep path."""
        original = "/Users/samotage/dev/otagelabs/claude/headspace"
        encoded = encode_project_path(original)
        decoded = decode_project_path(encoded)
        assert decoded == original


class TestLocateJsonlFile:
    """Test locate_jsonl_file function."""

    def test_locate_existing_file(self):
        """Test locating existing jsonl file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create structure
            projects_path = tmpdir
            folder_name = encode_project_path("/test/project")
            project_folder = os.path.join(projects_path, folder_name)
            os.makedirs(project_folder)

            # Create jsonl file
            jsonl_path = os.path.join(project_folder, "session.jsonl")
            with open(jsonl_path, "w") as f:
                f.write('{"test": "data"}\n')

            # Locate file
            result = locate_jsonl_file("/test/project", projects_path)
            assert result == jsonl_path

    def test_locate_most_recent_file(self):
        """Test locating most recent jsonl file when multiple exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            projects_path = tmpdir
            folder_name = encode_project_path("/test/project")
            project_folder = os.path.join(projects_path, folder_name)
            os.makedirs(project_folder)

            # Create older file
            older_path = os.path.join(project_folder, "old.jsonl")
            with open(older_path, "w") as f:
                f.write('{"old": true}\n')

            # Small delay and create newer file
            import time
            time.sleep(0.1)
            newer_path = os.path.join(project_folder, "new.jsonl")
            with open(newer_path, "w") as f:
                f.write('{"new": true}\n')

            result = locate_jsonl_file("/test/project", projects_path)
            assert result == newer_path

    def test_locate_missing_folder(self):
        """Test locating file when folder doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = locate_jsonl_file("/nonexistent/project", tmpdir)
            assert result is None

    def test_locate_empty_folder(self):
        """Test locating file when folder is empty."""
        with tempfile.TemporaryDirectory() as tmpdir:
            projects_path = tmpdir
            folder_name = encode_project_path("/test/project")
            project_folder = os.path.join(projects_path, folder_name)
            os.makedirs(project_folder)

            result = locate_jsonl_file("/test/project", projects_path)
            assert result is None
