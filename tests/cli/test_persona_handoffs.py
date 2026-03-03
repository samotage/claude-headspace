"""Tests for ``flask persona handoffs`` CLI command."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from claude_headspace.cli.persona_cli import (
    _parse_handoff_filename,
    handoffs_command,
    persona_cli,
)


class TestParseHandoffFilename:
    """Tests for filename parsing logic."""

    def test_new_format(self):
        parsed = _parse_handoff_filename(
            "2026-01-15T14:30:00_refactored-auth-module_agent-id:1137.md"
        )

        assert parsed is not None
        assert parsed["timestamp"] == "2026-01-15T14:30:00"
        assert parsed["summary"] == "refactored-auth-module"
        assert parsed["agent_id"] == "1137"
        assert parsed["format"] == "new"

    def test_new_format_placeholder(self):
        parsed = _parse_handoff_filename(
            "2026-01-15T14:30:00_<insert-summary>_agent-id:42.md"
        )

        assert parsed is not None
        assert parsed["summary"] == "<insert-summary>"
        assert parsed["agent_id"] == "42"

    def test_legacy_format(self):
        parsed = _parse_handoff_filename("20260115T143000-00001137.md")

        assert parsed is not None
        assert parsed["timestamp"] == "2026-01-15T14:30:00"
        assert parsed["summary"] == "(legacy)"
        assert parsed["agent_id"] == "1137"  # Leading zeros stripped
        assert parsed["format"] == "legacy"

    def test_legacy_format_small_id(self):
        parsed = _parse_handoff_filename("20260101T120000-00000007.md")

        assert parsed is not None
        assert parsed["agent_id"] == "7"

    def test_unknown_format(self):
        parsed = _parse_handoff_filename("random-file.md")

        assert parsed is None

    def test_non_md_extension(self):
        parsed = _parse_handoff_filename(
            "2026-01-15T14:30:00_some-summary_agent-id:1.txt"
        )

        assert parsed is None


class TestHandoffsCommand:
    """Tests for flask persona handoffs command."""

    @pytest.fixture
    def runner(self, app):
        return app.test_cli_runner()

    @pytest.fixture
    def handoff_dir(self, app, tmp_path):
        """Create a handoff directory with test files."""
        app.config["PERSONA_DATA_ROOT"] = str(tmp_path)
        slug = "developer-con-1"
        d = tmp_path / slug / "handoffs"
        d.mkdir(parents=True)

        # Create new format files
        (d / "2026-01-03T10:00:00_third-task_agent-id:103.md").write_text("# 3")
        (d / "2026-01-01T10:00:00_first-task_agent-id:101.md").write_text("# 1")
        (d / "2026-01-02T10:00:00_second-task_agent-id:102.md").write_text("# 2")

        # Create legacy format file
        (d / "20251231T090000-00000100.md").write_text("# Legacy")

        return d

    def test_basic_listing(self, runner, handoff_dir):
        """Should list handoffs newest first."""
        with patch(
            "claude_headspace.cli.persona_cli.Persona"
        ) as mock_persona_cls:
            mock_persona = MagicMock()
            mock_persona.slug = "developer-con-1"
            mock_persona_cls.query.filter_by.return_value.first.return_value = (
                mock_persona
            )

            result = runner.invoke(persona_cli, ["handoffs", "developer-con-1"])

        assert result.exit_code == 0
        lines = result.output.strip().split("\n")
        # Header + separator + 4 data rows + summary = 7 lines
        assert len(lines) >= 6
        # Should say "4 handoffs"
        assert "4 handoffs" in result.output
        # Newest first — first data row should be 2026-01-03
        assert "2026-01-03" in lines[2]

    def test_limit_option(self, runner, handoff_dir):
        """--limit N should restrict output."""
        with patch(
            "claude_headspace.cli.persona_cli.Persona"
        ) as mock_persona_cls:
            mock_persona = MagicMock()
            mock_persona.slug = "developer-con-1"
            mock_persona_cls.query.filter_by.return_value.first.return_value = (
                mock_persona
            )

            result = runner.invoke(
                persona_cli, ["handoffs", "developer-con-1", "--limit", "2"]
            )

        assert result.exit_code == 0
        assert "2 handoffs" in result.output
        # Should show only the 2 newest
        assert "2026-01-03" in result.output
        assert "2026-01-02" in result.output
        assert "2026-01-01" not in result.output

    def test_paths_option(self, runner, handoff_dir):
        """--paths should include absolute file paths."""
        with patch(
            "claude_headspace.cli.persona_cli.Persona"
        ) as mock_persona_cls:
            mock_persona = MagicMock()
            mock_persona.slug = "developer-con-1"
            mock_persona_cls.query.filter_by.return_value.first.return_value = (
                mock_persona
            )

            result = runner.invoke(
                persona_cli, ["handoffs", "developer-con-1", "--paths"]
            )

        assert result.exit_code == 0
        # Header should include Path
        assert "Path" in result.output
        # Output should include absolute paths
        assert str(handoff_dir) in result.output

    def test_legacy_format_shows_legacy_label(self, runner, handoff_dir):
        """Legacy filenames should show (legacy) in summary column."""
        with patch(
            "claude_headspace.cli.persona_cli.Persona"
        ) as mock_persona_cls:
            mock_persona = MagicMock()
            mock_persona.slug = "developer-con-1"
            mock_persona_cls.query.filter_by.return_value.first.return_value = (
                mock_persona
            )

            result = runner.invoke(persona_cli, ["handoffs", "developer-con-1"])

        assert result.exit_code == 0
        assert "(legacy)" in result.output

    def test_invalid_persona_slug(self, runner, app, tmp_path):
        """Invalid persona slug should show error."""
        app.config["PERSONA_DATA_ROOT"] = str(tmp_path)
        with patch(
            "claude_headspace.cli.persona_cli.Persona"
        ) as mock_persona_cls:
            mock_persona_cls.query.filter_by.return_value.first.return_value = None

            result = runner.invoke(persona_cli, ["handoffs", "nonexistent"])

        assert result.exit_code != 0

    def test_no_handoffs(self, runner, app, tmp_path):
        """No handoff files should show appropriate message."""
        app.config["PERSONA_DATA_ROOT"] = str(tmp_path)
        slug = "developer-con-1"
        d = tmp_path / slug / "handoffs"
        d.mkdir(parents=True)

        with patch(
            "claude_headspace.cli.persona_cli.Persona"
        ) as mock_persona_cls:
            mock_persona = MagicMock()
            mock_persona.slug = slug
            mock_persona_cls.query.filter_by.return_value.first.return_value = (
                mock_persona
            )

            result = runner.invoke(persona_cli, ["handoffs", slug])

        assert result.exit_code == 0
        assert "No handoffs found" in result.output
