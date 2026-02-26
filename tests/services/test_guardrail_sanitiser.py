"""Unit tests for error output sanitisation service.

Tests that sanitise_error_output() strips file paths, stack traces,
module names, environment details, and process IDs from text while
preserving generic failure messages.
"""

import pytest

from claude_headspace.services.guardrail_sanitiser import (
    contains_error_patterns,
    sanitise_error_output,
)


class TestSanitiseErrorOutput:
    """Test the main sanitisation function."""

    def test_empty_string_unchanged(self):
        assert sanitise_error_output("") == ""

    def test_none_returns_none(self):
        assert sanitise_error_output(None) is None

    def test_strips_absolute_paths(self):
        text = "Error at /Users/samotage/dev/project/src/module.py"
        result = sanitise_error_output(text)
        assert "/Users/samotage" not in result
        assert "/dev/project" not in result
        assert "module.py" not in result

    def test_strips_python_traceback(self):
        text = (
            "Traceback (most recent call last):\n"
            '  File "/home/user/app/main.py", line 42, in run\n'
            "    result = do_thing()\n"
            '  File "/home/user/app/lib/worker.py", line 10, in do_thing\n'
            "    raise ValueError('bad input')\n"
            "ValueError: bad input"
        )
        result = sanitise_error_output(text)
        assert "/home/user/app" not in result
        assert "main.py" not in result
        assert "worker.py" not in result
        assert "line 42" not in result

    def test_strips_module_dotted_names(self):
        text = "claude_headspace.services.skill_injector: injection failed"
        result = sanitise_error_output(text)
        assert "claude_headspace.services.skill_injector" not in result

    def test_strips_process_ids(self):
        text = "Worker crashed (pid=12345)"
        result = sanitise_error_output(text)
        assert "pid=12345" not in result

    def test_strips_pid_colon_format(self):
        text = "Process PID: 54321 exited"
        result = sanitise_error_output(text)
        assert "PID: 54321" not in result

    def test_strips_venv_paths(self):
        text = "Error in venv/lib/python3.10/site-packages/flask/app.py"
        result = sanitise_error_output(text)
        assert "venv" not in result
        assert "site-packages" not in result

    def test_strips_python_version(self):
        text = "Running on Python 3.10.4 with Flask 3.0"
        result = sanitise_error_output(text)
        assert "Python 3.10.4" not in result

    def test_strips_env_variables(self):
        text = "DATABASE_URL=postgresql://user:pass@host/db"
        result = sanitise_error_output(text)
        assert "DATABASE_URL=postgresql" not in result

    def test_preserves_generic_failure_message(self):
        """Generic failure messages should survive sanitisation."""
        text = "The operation failed. Please try again later."
        result = sanitise_error_output(text)
        assert "operation failed" in result
        assert "try again" in result

    def test_preserves_user_facing_text(self):
        """Normal user-facing text without system details passes through."""
        text = "I'm having trouble completing that request. Let me try another approach."
        result = sanitise_error_output(text)
        assert result == text

    def test_strips_traceback_preserves_error_type(self):
        """After stripping traceback, we get a redaction but the text is clean."""
        text = (
            "Command failed:\n"
            "Traceback (most recent call last):\n"
            '  File "/app/src/thing.py", line 5, in go\n'
            "    raise RuntimeError('oops')\n"
            "RuntimeError: oops\n"
            "\n"
            "Please retry."
        )
        result = sanitise_error_output(text)
        assert "/app/src/thing.py" not in result
        assert "Command failed" in result
        assert "Please retry" in result

    def test_collapses_multiple_redactions(self):
        """Multiple consecutive redactions are collapsed into one."""
        text = (
            "Error at /a/b/c.py in /d/e/f.py near /g/h/i.py"
        )
        result = sanitise_error_output(text)
        # Should not have multiple consecutive [details redacted]
        assert "[details redacted]  [details redacted]" not in result

    def test_real_world_sqlalchemy_error(self):
        """Test with a realistic SQLAlchemy error output."""
        text = (
            "sqlalchemy.exc.ProgrammingError: (psycopg2.errors.UndefinedColumn) "
            "column agents.guardrails_version_hash does not exist\n"
            "LINE 1: ...prompt_injected_at AS agents_prompt_injected_at, agents.gua...\n"
            "                                                             ^\n"
            "\n"
            "[SQL: SELECT agents.id AS agents_id, agents.session_uuid FROM agents]\n"
            "(Background on this error at: https://sqlalche.me/e/20/f405)"
        )
        result = sanitise_error_output(text)
        assert "sqlalchemy.exc.ProgrammingError" not in result
        assert "psycopg2.errors.UndefinedColumn" not in result


class TestContainsErrorPatterns:
    """Test error pattern detection."""

    def test_detects_traceback(self):
        assert contains_error_patterns("Traceback (most recent call last):")

    def test_detects_error_colon(self):
        assert contains_error_patterns("ValueError: bad input")

    def test_detects_exception(self):
        assert contains_error_patterns("RuntimeException: something broke")

    def test_detects_failed_keyword(self):
        assert contains_error_patterns("Command FAILED with exit code 1")

    def test_normal_text_no_error(self):
        assert not contains_error_patterns("Everything is working fine.")

    def test_empty_text(self):
        assert not contains_error_patterns("")

    def test_none_text(self):
        assert not contains_error_patterns(None)

    def test_path_with_error_keyword(self):
        text = "Operation failed at /usr/local/bin/tool"
        assert contains_error_patterns(text)
