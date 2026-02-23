"""Tests for team_content_detector."""

import json
import pytest

from claude_headspace.services.team_content_detector import (
    filter_skill_expansion,
    is_team_internal_content,
)


class TestXMLDetection:
    """Test detection of XML tags from Claude Code sub-agent injection."""

    def test_task_notification(self):
        assert is_team_internal_content("<task-notification>Agent completed work</task-notification>")

    def test_system_reminder(self):
        assert is_team_internal_content("<system-reminder>Context info here</system-reminder>")

    def test_task_notification_mid_text_is_not_internal(self):
        """Tags mentioned mid-text are discussion, not protocol content."""
        assert not is_team_internal_content("Some prefix <task-notification>payload</task-notification> suffix")

    def test_tag_mentioned_in_backticks_is_not_internal(self):
        """Agent discussing tags in prose should not be flagged."""
        assert not is_team_internal_content("Detects `<task-notification>` and `<system-reminder>` XML tags")

    def test_tag_with_closing_tag_mid_text_is_not_internal(self):
        """Even with both open+close tags, mid-text mentions are not internal."""
        assert not is_team_internal_content(
            "The detector checks for <task-notification> and </task-notification> patterns"
        )

    def test_system_reminder_with_attributes(self):
        assert is_team_internal_content('<system-reminder foo="bar">content</system-reminder>')


class TestSendMessageJSON:
    """Test detection of SendMessage JSON payloads."""

    def test_direct_message(self):
        msg = json.dumps({
            "type": "message",
            "recipient": "researcher",
            "content": "Found the issue in auth module",
            "summary": "Auth module issue found",
        })
        assert is_team_internal_content(msg)

    def test_message_without_recipient_is_not_internal(self):
        """A JSON with type=message but no recipient is not a SendMessage."""
        msg = json.dumps({"type": "message", "content": "hello"})
        assert not is_team_internal_content(msg)


class TestBroadcastJSON:
    """Test detection of broadcast messages."""

    def test_broadcast(self):
        msg = json.dumps({
            "type": "broadcast",
            "content": "Critical blocking issue found",
            "summary": "Blocking issue",
        })
        assert is_team_internal_content(msg)

    def test_broadcast_without_content_is_not_internal(self):
        msg = json.dumps({"type": "broadcast"})
        assert not is_team_internal_content(msg)


class TestShutdownJSON:
    """Test detection of shutdown request/response."""

    def test_shutdown_request(self):
        msg = json.dumps({
            "type": "shutdown_request",
            "recipient": "researcher",
            "content": "Task complete, wrapping up",
        })
        assert is_team_internal_content(msg)

    def test_shutdown_response(self):
        msg = json.dumps({
            "type": "shutdown_response",
            "request_id": "abc-123",
            "approve": True,
        })
        assert is_team_internal_content(msg)


class TestPlanApprovalJSON:
    """Test detection of plan approval request/response."""

    def test_plan_approval_request(self):
        msg = json.dumps({
            "type": "plan_approval_request",
            "request_id": "abc-123",
        })
        assert is_team_internal_content(msg)

    def test_plan_approval_response(self):
        msg = json.dumps({
            "type": "plan_approval_response",
            "request_id": "abc-123",
            "recipient": "researcher",
            "approve": True,
        })
        assert is_team_internal_content(msg)


class TestIdleJSON:
    """Test detection of idle notifications."""

    def test_idle_notification(self):
        msg = json.dumps({"type": "idle"})
        assert is_team_internal_content(msg)

    def test_idle_with_extra_fields(self):
        msg = json.dumps({"type": "idle", "agent": "researcher", "timestamp": "2026-02-16T12:00:00Z"})
        assert is_team_internal_content(msg)


class TestNoFalsePositives:
    """Ensure normal user text is NOT flagged as internal."""

    def test_none(self):
        assert not is_team_internal_content(None)

    def test_empty(self):
        assert not is_team_internal_content("")

    def test_whitespace(self):
        assert not is_team_internal_content("   ")

    def test_normal_user_text(self):
        assert not is_team_internal_content("Please fix the login bug in auth.py")

    def test_text_mentioning_type_message(self):
        """User text that mentions 'type' and 'message' should not trigger."""
        assert not is_team_internal_content('The type of message should be "error"')

    def test_json_with_unknown_type(self):
        msg = json.dumps({"type": "unknown", "data": "test"})
        assert not is_team_internal_content(msg)

    def test_json_array(self):
        msg = json.dumps([{"type": "message", "recipient": "test"}])
        assert not is_team_internal_content(msg)

    def test_partial_json(self):
        assert not is_team_internal_content('{"type": "message", "recipient": ')

    def test_html_tags_not_matching(self):
        assert not is_team_internal_content("<div>some html</div>")

    def test_code_block_with_type_keyword(self):
        """Code blocks mentioning types should not trigger."""
        assert not is_team_internal_content('```\nconst type = "message";\n```')

    def test_regular_json_object(self):
        msg = json.dumps({"name": "test", "value": 42})
        assert not is_team_internal_content(msg)


class TestFilterSkillExpansion:
    """Test filter_skill_expansion truncation of command .md content."""

    SKILL_TEXT = (
        "# 40: PRD Test\n\n"
        "**Command name:** `40: prd-test`\n\n"
        "**Purpose:** Fresh sub-agent for TEST phase.\n\n"
        "---\n\n## Prompt\n\n" + "x" * 500
    )

    def test_truncates_skill_expansion(self):
        result = filter_skill_expansion(self.SKILL_TEXT)
        assert result == "# 40: PRD Test"

    def test_short_text_unchanged(self):
        assert filter_skill_expansion("fix the bug") == "fix the bug"

    def test_none_returns_none(self):
        assert filter_skill_expansion(None) is None

    def test_empty_returns_empty(self):
        assert filter_skill_expansion("") == ""

    def test_long_text_without_command_name_unchanged(self):
        long_text = "# My Long Prompt\n\n" + "paragraph " * 200
        assert filter_skill_expansion(long_text) == long_text

    def test_real_orch_command_pattern(self):
        text = (
            "# 30: PRD Proposal\n\n"
            "**Command name:** `30: prd-proposal`\n\n"
            "**Purpose:** Fresh sub-agent for PREPARE phase.\n\n"
            "---\n\n## Prompt\n\n"
            "You are a fresh sub-agent handling the PREPARE phase. " * 50
        )
        assert filter_skill_expansion(text) == "# 30: PRD Proposal"

    def test_orch_v2_lead_command(self):
        """New-format orch commands (heading + --- + ## sections) should be filtered."""
        text = (
            "# PRD Orchestration Lead\n\n"
            "You are the persistent orchestration lead. You manage the full PRD processing "
            "pipeline by spawning foreground worker agents via the `Task` tool for each phase, "
            "handling all checkpoints, and maintaining state recovery.\n\n"
            "**Key principles:**\n"
            "- You spawn workers using `Task(subagent_type=\"general-purpose\")`\n\n"
            "---\n\n"
            "## Step 1: Resume Detection\n\n"
            "Check if a previous run was interrupted.\n\n"
            "```bash\nruby orch/orchestrator.rb state show\n```\n\n"
            "---\n\n"
            "## Step 2: Queue Check\n\n" + "x" * 200
        )
        assert filter_skill_expansion(text) == "# PRD Orchestration Lead"

    def test_orch_v2_queue_status(self):
        """Queue status utility command should be filtered."""
        text = (
            "# Queue Status\n\n"
            "Display the current PRD orchestration status.\n\n"
            "---\n\n"
            "## Get Status\n\n"
            "```bash\nruby orch/orchestrator.rb status\n```\n\n"
            "---\n\n"
            "## Display\n\n" + "x" * 500
        )
        assert filter_skill_expansion(text) == "# Queue Status"

    def test_regular_long_markdown_not_filtered(self):
        """Long user prompts with markdown headings should NOT be filtered."""
        text = "# Please help me refactor this\n\n" + "code line\n" * 200
        assert filter_skill_expansion(text) == text
