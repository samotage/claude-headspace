"""Tests for voice bridge channel routing extensions (e9-s8).

Tests cover:
- Channel intent detection (regex patterns)
- Channel name matching (fuzzy matching algorithm)
- Channel context tracking (per-session state)
- VoiceFormatter channel methods
- Integration with voice_command() endpoint
"""

from types import SimpleNamespace

import pytest

from src.claude_headspace.routes.voice_bridge import (
    _channel_context,
    _detect_channel_intent,
    _extract_member_refs,
    _get_channel_context,
    _infer_channel_type,
    _match_channel,
    _resolve_channel_ref,
    _set_channel_context,
)
from src.claude_headspace.services.voice_formatter import VoiceFormatter

# ── Fixtures ──────────────────────────────────────────────────────


@pytest.fixture
def formatter():
    """Create a VoiceFormatter for channel tests."""
    return VoiceFormatter(config={"voice_bridge": {"default_verbosity": "concise"}})


@pytest.fixture(autouse=True)
def clear_channel_context():
    """Clear channel context between tests."""
    _channel_context.clear()
    yield
    _channel_context.clear()


def _make_channel(name, slug, status="active"):
    """Create a mock channel object."""
    ch = SimpleNamespace()
    ch.name = name
    ch.slug = slug
    ch.status = status
    ch.channel_type = SimpleNamespace(value="workshop")
    return ch


# ═══════════════════════════════════════════════════════════════════
# 3.1 Channel Intent Detection Tests
# ═══════════════════════════════════════════════════════════════════


class TestChannelIntentDetection:
    """Test _detect_channel_intent() pattern matching."""

    # 3.1.1 Test all 6 command types
    def test_send_action(self):
        result = _detect_channel_intent("send to workshop: hello world")
        assert result is not None
        assert result["action"] == "send"

    def test_history_action(self):
        result = _detect_channel_intent("what's happening in the workshop?")
        assert result is not None
        assert result["action"] == "history"

    def test_list_action(self):
        result = _detect_channel_intent("list channels")
        assert result is not None
        assert result["action"] == "list"

    def test_create_action(self):
        result = _detect_channel_intent("create a workshop channel called test")
        assert result is not None
        assert result["action"] == "create"

    def test_add_member_action(self):
        result = _detect_channel_intent("add Robbo to the workshop")
        assert result is not None
        assert result["action"] == "add_member"

    def test_complete_action(self):
        result = _detect_channel_intent("complete the workshop")
        assert result is not None
        assert result["action"] == "complete"

    # 3.1.2 Send patterns extract channel_ref and content
    def test_send_with_channel_keyword(self):
        result = _detect_channel_intent("send to workshop channel: hello")
        assert result["action"] == "send"
        assert result["channel_ref"] == "workshop"
        assert result["content"] == "hello"

    def test_message_pattern(self):
        result = _detect_channel_intent("message persona alignment: I disagree")
        assert result["action"] == "send"
        assert result["content"] == "I disagree"

    def test_tell_pattern(self):
        result = _detect_channel_intent("tell the workshop: we need to pivot")
        assert result["action"] == "send"
        assert result["content"] == "we need to pivot"

    # 3.1.3 History patterns extract channel_ref
    def test_whats_happening(self):
        result = _detect_channel_intent("what's happening in the workshop?")
        assert result["action"] == "history"
        assert result["channel_ref"] == "workshop"

    def test_whats_going_on(self):
        result = _detect_channel_intent("whats going on in persona alignment?")
        assert result["action"] == "history"
        assert result["channel_ref"] == "persona alignment"

    def test_show_messages(self):
        result = _detect_channel_intent("show workshop messages")
        assert result["action"] == "history"
        assert result["channel_ref"] == "workshop"

    def test_channel_history_for(self):
        result = _detect_channel_intent("history for the workshop")
        assert result["action"] == "history"
        assert result["channel_ref"] == "workshop"

    # 3.1.4 Create patterns extract type, name, and member_refs
    def test_create_typed_channel(self):
        result = _detect_channel_intent(
            "create a delegation channel called auth refactor"
        )
        assert result["action"] == "create"
        assert result["channel_type"] == "delegation"
        assert result["name"] == "auth refactor"

    def test_create_with_members(self):
        result = _detect_channel_intent(
            "create a workshop channel called persona alignment with Robbo and Paula"
        )
        assert result["action"] == "create"
        assert result["channel_type"] == "workshop"
        assert result["name"] == "persona alignment"
        assert result["member_refs"] == ["Robbo", "Paula"]

    # 3.1.5 Add member patterns
    def test_add_member_to_named_channel(self):
        result = _detect_channel_intent("add Robbo to the workshop")
        assert result["action"] == "add_member"
        assert result["member_ref"] == "Robbo"
        assert "workshop" in result["channel_ref"]

    def test_add_member_to_this_channel(self):
        result = _detect_channel_intent("add Con to this channel")
        assert result["action"] == "add_member"
        assert result["member_ref"] == "Con"
        assert result["channel_ref"] == "this channel"

    # 3.1.6 Complete patterns
    def test_complete_channel(self):
        result = _detect_channel_intent("complete the persona alignment channel")
        assert result["action"] == "complete"
        assert "persona alignment" in result["channel_ref"]

    def test_finish_channel(self):
        result = _detect_channel_intent("finish the workshop")
        assert result["action"] == "complete"

    def test_close_channel(self):
        result = _detect_channel_intent("close the workshop")
        assert result["action"] == "complete"

    # 3.1.7 List patterns
    def test_list_channels(self):
        assert _detect_channel_intent("list channels")["action"] == "list"

    def test_show_channels(self):
        assert _detect_channel_intent("show channels")["action"] == "list"

    def test_my_channels(self):
        assert _detect_channel_intent("my channels")["action"] == "list"

    def test_what_channels_am_i_in(self):
        assert _detect_channel_intent("what channels am I in?")["action"] == "list"

    # 3.1.8 Non-channel utterances return None
    def test_agent_command_returns_none(self):
        assert _detect_channel_intent("run the test suite") is None

    def test_simple_text_returns_none(self):
        assert _detect_channel_intent("hello world") is None

    def test_status_check_returns_none(self):
        assert _detect_channel_intent("what are you working on?") is None


# ═══════════════════════════════════════════════════════════════════
# 3.2 Channel Name Matching Tests
# ═══════════════════════════════════════════════════════════════════


class TestChannelNameMatching:
    """Test _match_channel() fuzzy matching."""

    def setup_method(self):
        self.channels = [
            _make_channel("Persona Alignment Workshop", "workshop-persona-alignment-7"),
            _make_channel("API Design Review", "review-api-design-12"),
            _make_channel("Auth Refactor", "delegation-auth-refactor-3"),
        ]

    # 3.2.1 Exact slug match
    def test_exact_slug_match(self):
        result = _match_channel("workshop-persona-alignment-7", self.channels)
        assert "match" in result
        assert result["confidence"] == 1.0
        assert result["match"].slug == "workshop-persona-alignment-7"

    # 3.2.2 Exact name match (case-insensitive)
    def test_exact_name_match(self):
        result = _match_channel("persona alignment workshop", self.channels)
        assert "match" in result
        assert result["confidence"] == 1.0

    def test_exact_name_match_case_insensitive(self):
        result = _match_channel("PERSONA ALIGNMENT WORKSHOP", self.channels)
        assert "match" in result
        assert result["confidence"] == 1.0

    # 3.2.3 Substring match
    def test_substring_match(self):
        result = _match_channel("persona alignment", self.channels)
        assert "match" in result
        assert result["match"].name == "Persona Alignment Workshop"

    def test_slug_substring_match(self):
        result = _match_channel("api-design", self.channels)
        assert "match" in result
        assert result["match"].slug == "review-api-design-12"

    # 3.2.4 Token overlap
    def test_token_overlap(self):
        result = _match_channel("alignment persona", self.channels)
        assert "match" in result or "ambiguous" in result
        if "match" in result:
            assert (
                "persona" in result["match"].name.lower()
                or "alignment" in result["match"].name.lower()
            )

    # 3.2.5 Ambiguous matches
    def test_ambiguous_matches(self):
        # Create channels with similar names
        channels = [
            _make_channel("Workshop Alpha", "workshop-alpha-1"),
            _make_channel("Workshop Beta", "workshop-beta-2"),
        ]
        result = _match_channel("workshop", channels)
        assert "ambiguous" in result
        assert len(result["ambiguous"]) >= 2

    # 3.2.6 No match
    def test_no_match(self):
        result = _match_channel("nonexistent channel", self.channels)
        assert "no_match" in result

    # 3.2.7 Article stripping
    def test_article_stripping_the(self):
        result = _match_channel("the persona alignment workshop", self.channels)
        assert "match" in result
        assert result["match"].name == "Persona Alignment Workshop"

    def test_article_stripping_a(self):
        result = _match_channel("a workshop", self.channels)
        # Should match via substring
        assert "match" in result or "ambiguous" in result

    # 3.2.8 Speech-to-text artifact tolerance
    def test_punctuation_removal(self):
        result = _match_channel("persona alignment?", self.channels)
        assert "match" in result

    def test_trailing_period(self):
        result = _match_channel("persona alignment.", self.channels)
        assert "match" in result


# ═══════════════════════════════════════════════════════════════════
# 3.3 Channel Context Tests
# ═══════════════════════════════════════════════════════════════════


class TestChannelContext:
    """Test channel context tracking."""

    # 3.3.1 Set and get
    def test_set_and_get(self):
        _set_channel_context("token123", "workshop-alpha-1")
        assert _get_channel_context("token123") == "workshop-alpha-1"

    # 3.3.2 "this channel" resolves
    def test_this_channel_resolves(self):
        _set_channel_context("token123", "workshop-alpha-1")
        result = _resolve_channel_ref("this channel", "token123")
        assert result == "workshop-alpha-1"

    def test_the_channel_resolves(self):
        _set_channel_context("token123", "workshop-alpha-1")
        result = _resolve_channel_ref("the channel", "token123")
        assert result == "workshop-alpha-1"

    def test_current_channel_resolves(self):
        _set_channel_context("token123", "workshop-alpha-1")
        result = _resolve_channel_ref("current channel", "token123")
        assert result == "workshop-alpha-1"

    # 3.3.3 "this channel" raises ValueError without context
    def test_this_channel_no_context_raises(self):
        with pytest.raises(ValueError, match="No current channel context"):
            _resolve_channel_ref("this channel", "token_no_context")

    # 3.3.4 Independent contexts per token
    def test_independent_contexts(self):
        _set_channel_context("token_a", "channel-a")
        _set_channel_context("token_b", "channel-b")
        assert _get_channel_context("token_a") == "channel-a"
        assert _get_channel_context("token_b") == "channel-b"

    def test_non_context_ref_passes_through(self):
        result = _resolve_channel_ref("workshop channel", "token123")
        assert result == "workshop channel"


# ═══════════════════════════════════════════════════════════════════
# 3.4 VoiceFormatter Channel Tests
# ═══════════════════════════════════════════════════════════════════


class TestVoiceFormatterChannels:
    """Test VoiceFormatter channel formatting methods."""

    # 3.4.1 format_channel_message_sent
    def test_message_sent(self, formatter):
        result = formatter.format_channel_message_sent("workshop-alpha-1")
        assert result["status_line"] == "Message sent to #workshop-alpha-1."
        assert result["results"] == []
        assert result["next_action"] == "none"

    # 3.4.2 format_channel_history
    def test_history_with_messages(self, formatter):
        messages = [
            {"persona_name": "Robbo", "content": "Hello world"},
            {"persona_name": "Paula", "content": "Hi there"},
        ]
        result = formatter.format_channel_history("workshop-alpha-1", messages)
        assert "Last 2 messages" in result["status_line"]
        assert len(result["results"]) == 2
        assert "Robbo: Hello world" in result["results"][0]

    def test_history_empty(self, formatter):
        result = formatter.format_channel_history("workshop-alpha-1", [])
        assert "No messages" in result["status_line"]

    def test_history_concise_truncates(self, formatter):
        long_content = "A" * 100
        messages = [{"persona_name": "Test", "content": long_content}]
        result = formatter.format_channel_history("slug", messages, verbosity="concise")
        assert result["results"][0].endswith("...")

    # 3.4.3 format_channel_created
    def test_channel_created(self, formatter):
        members = ["Robbo joined.", "Paula -- agent spinning up."]
        result = formatter.format_channel_created(
            "workshop-alpha-1", "workshop", members
        )
        assert "Created channel #workshop-alpha-1" in result["status_line"]
        assert "(workshop)" in result["status_line"]
        assert result["results"] == members

    # 3.4.4 format_channel_completed
    def test_channel_completed(self, formatter):
        result = formatter.format_channel_completed("workshop-alpha-1")
        assert result["status_line"] == "Channel #workshop-alpha-1 completed."
        assert result["results"] == []

    # 3.4.5 format_channel_list
    def test_channel_list_with_channels(self, formatter):
        channels = [
            {
                "slug": "workshop-alpha-1",
                "channel_type": "workshop",
                "status": "active",
            },
            {"slug": "review-beta-2", "channel_type": "review", "status": "pending"},
        ]
        result = formatter.format_channel_list(channels)
        assert "2 active channels" in result["status_line"]
        assert len(result["results"]) == 2

    def test_channel_list_empty(self, formatter):
        result = formatter.format_channel_list([])
        assert "No active channels" in result["status_line"]
        assert "Create a channel" in result["next_action"]

    def test_channel_list_singular(self, formatter):
        channels = [{"slug": "x", "channel_type": "workshop", "status": "active"}]
        result = formatter.format_channel_list(channels)
        assert "1 active channel." in result["status_line"]

    # 3.4.6 format_channel_member_added
    def test_member_added(self, formatter):
        result = formatter.format_channel_member_added("Robbo", "workshop-alpha-1")
        assert "Robbo added to #workshop-alpha-1" in result["status_line"]
        assert "(agent spinning up)" not in result["status_line"]

    def test_member_added_spinning_up(self, formatter):
        result = formatter.format_channel_member_added(
            "Robbo", "workshop-alpha-1", spinning_up=True
        )
        assert "(agent spinning up)" in result["status_line"]


# ═══════════════════════════════════════════════════════════════════
# Helper function tests
# ═══════════════════════════════════════════════════════════════════


class TestHelperFunctions:
    """Test channel helper functions."""

    def test_infer_channel_type_workshop(self):
        assert _infer_channel_type("create a workshop channel") == "workshop"

    def test_infer_channel_type_delegation(self):
        assert _infer_channel_type("delegation for auth refactor") == "delegation"

    def test_infer_channel_type_review(self):
        assert _infer_channel_type("review channel for PR") == "review"

    def test_infer_channel_type_default(self):
        assert _infer_channel_type("some random text") == "workshop"

    def test_infer_channel_type_standup(self):
        assert _infer_channel_type("daily standup") == "standup"

    def test_infer_channel_type_broadcast(self):
        assert _infer_channel_type("announcement to the team") == "broadcast"

    def test_extract_member_refs_and(self):
        assert _extract_member_refs("Robbo and Paula") == ["Robbo", "Paula"]

    def test_extract_member_refs_comma(self):
        assert _extract_member_refs("Robbo, Paula, Con") == ["Robbo", "Paula", "Con"]

    def test_extract_member_refs_ampersand(self):
        assert _extract_member_refs("Robbo & Paula") == ["Robbo", "Paula"]

    def test_extract_member_refs_empty(self):
        assert _extract_member_refs("") == []

    def test_extract_member_refs_none(self):
        assert _extract_member_refs(None) == []

    def test_extract_member_refs_single(self):
        assert _extract_member_refs("Robbo") == ["Robbo"]
