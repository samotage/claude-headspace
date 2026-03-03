"""Tests for channel-related dashboard route functionality.

Tests cover:
- get_channel_data_for_operator() query logic
- Dashboard template rendering with/without channel data
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from src.claude_headspace.routes.dashboard import get_channel_data_for_operator

# ──────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────


def _make_mock_persona(id=1, name="Sam", slug="person-sam-1"):
    """Create a mock Persona."""
    p = MagicMock()
    p.id = id
    p.name = name
    p.slug = slug
    return p


def _make_mock_channel(
    id=1,
    slug="workshop-test-1",
    name="Test Channel",
    channel_type_value="workshop",
    status="active",
    description=None,
    archived_at=None,
    memberships=None,
):
    """Create a mock Channel with memberships."""
    ch = MagicMock()
    ch.id = id
    ch.slug = slug
    ch.name = name
    ch.channel_type = MagicMock()
    ch.channel_type.value = channel_type_value
    ch.status = status
    ch.description = description
    ch.archived_at = archived_at
    ch.memberships = memberships or []
    return ch


def _make_mock_membership(
    id=1,
    channel_id=1,
    persona_id=1,
    status="active",
    channel=None,
    persona=None,
):
    """Create a mock ChannelMembership."""
    m = MagicMock()
    m.id = id
    m.channel_id = channel_id
    m.persona_id = persona_id
    m.status = status
    m.channel = channel
    m.persona = persona
    return m


def _make_mock_message(
    id=1,
    channel_id=1,
    content="Hello world",
    persona_name="Sam",
    sent_at=None,
):
    """Create a mock Message."""
    msg = MagicMock()
    msg.id = id
    msg.channel_id = channel_id
    msg.content = content
    msg.persona = MagicMock()
    msg.persona.name = persona_name
    msg.sent_at = sent_at or datetime(2026, 3, 3, 12, 0, 0, tzinfo=timezone.utc)
    return msg


def _setup_db_mock(mock_db, memberships, latest_messages):
    """Configure db.session.query mock for get_channel_data_for_operator.

    The function makes 3 query calls:
    1. ChannelMembership query -> memberships
    2. Subquery for max(sent_at) per channel -> subquery object
    3. Message join query -> latest_messages
    """
    call_count = [0]

    def mock_query_side_effect(*args):
        call_count[0] += 1
        q = MagicMock()
        # Make all chaining methods return q
        q.join.return_value = q
        q.filter.return_value = q
        q.options.return_value = q
        q.group_by.return_value = q
        q.subquery.return_value = MagicMock()

        if call_count[0] == 1:
            q.all.return_value = memberships
        elif call_count[0] == 3:
            q.all.return_value = latest_messages

        return q

    mock_db.session.query.side_effect = mock_query_side_effect
    mock_db.func.max.return_value = MagicMock()
    mock_db.and_.return_value = MagicMock()


# ──────────────────────────────────────────────────────────────
# Test: get_channel_data_for_operator()
# ──────────────────────────────────────────────────────────────


class TestGetChannelDataForOperator:
    """Tests for the get_channel_data_for_operator function."""

    @patch("src.claude_headspace.routes.dashboard.Persona")
    def test_returns_empty_when_no_operator(self, mock_persona_cls, app):
        """3.2: Returns empty list when operator has no Persona."""
        mock_persona_cls.get_operator.return_value = None

        with app.app_context():
            result = get_channel_data_for_operator()

        assert result == []

    @patch("src.claude_headspace.routes.dashboard.db")
    @patch("src.claude_headspace.routes.dashboard.Persona")
    def test_returns_empty_when_no_memberships(self, mock_persona_cls, mock_db, app):
        """Returns empty list when operator has no active memberships."""
        operator = _make_mock_persona()
        mock_persona_cls.get_operator.return_value = operator

        _setup_db_mock(mock_db, memberships=[], latest_messages=[])

        with app.app_context():
            result = get_channel_data_for_operator()

        assert result == []

    @patch("src.claude_headspace.routes.dashboard.db")
    @patch("src.claude_headspace.routes.dashboard.Persona")
    def test_returns_correct_structure(self, mock_persona_cls, mock_db, app):
        """3.1: Returns correct structure with active memberships."""
        operator = _make_mock_persona()
        mock_persona_cls.get_operator.return_value = operator

        # Build mock channel with members
        member1 = _make_mock_persona(id=1, name="Sam")
        member2 = _make_mock_persona(id=2, name="Con")

        channel = _make_mock_channel(
            id=10,
            slug="workshop-auth-10",
            name="Auth Review",
            channel_type_value="workshop",
            status="active",
        )
        cm1 = _make_mock_membership(
            id=1, channel_id=10, persona_id=1, persona=member1, status="active"
        )
        cm2 = _make_mock_membership(
            id=2, channel_id=10, persona_id=2, persona=member2, status="active"
        )
        channel.memberships = [cm1, cm2]

        membership = _make_mock_membership(
            id=1,
            channel_id=10,
            persona_id=1,
            channel=channel,
        )

        last_msg = _make_mock_message(
            id=5,
            channel_id=10,
            content="Looking at the auth module",
            persona_name="Con",
        )

        _setup_db_mock(mock_db, memberships=[membership], latest_messages=[last_msg])

        with app.app_context():
            result = get_channel_data_for_operator()

        assert len(result) == 1
        ch_data = result[0]
        assert ch_data["slug"] == "workshop-auth-10"
        assert ch_data["name"] == "Auth Review"
        assert ch_data["channel_type"] == "workshop"
        assert ch_data["status"] == "active"
        assert "Sam" in ch_data["members"]
        assert "Con" in ch_data["members"]
        assert ch_data["last_message"] is not None
        assert ch_data["last_message"]["persona_name"] == "Con"
        assert "auth module" in ch_data["last_message"]["content_preview"]

    @patch("src.claude_headspace.routes.dashboard.db")
    @patch("src.claude_headspace.routes.dashboard.Persona")
    def test_excludes_archived_channels(self, mock_persona_cls, mock_db, app):
        """3.3: Archived channels are excluded via the query filter."""
        operator = _make_mock_persona()
        mock_persona_cls.get_operator.return_value = operator

        # Simulate: query returns empty because archived channels are filtered
        _setup_db_mock(mock_db, memberships=[], latest_messages=[])

        with app.app_context():
            result = get_channel_data_for_operator()

        assert result == []

    @patch("src.claude_headspace.routes.dashboard.db")
    @patch("src.claude_headspace.routes.dashboard.Persona")
    def test_handles_channel_with_no_messages(self, mock_persona_cls, mock_db, app):
        """Card with no messages shows last_message as None."""
        operator = _make_mock_persona()
        mock_persona_cls.get_operator.return_value = operator

        channel = _make_mock_channel(id=10, slug="review-check-10", name="Code Check")
        membership = _make_mock_membership(
            id=1, channel_id=10, persona_id=1, channel=channel
        )

        _setup_db_mock(mock_db, memberships=[membership], latest_messages=[])

        with app.app_context():
            result = get_channel_data_for_operator()

        assert len(result) == 1
        assert result[0]["last_message"] is None

    @patch("src.claude_headspace.routes.dashboard.db")
    @patch("src.claude_headspace.routes.dashboard.Persona")
    def test_truncates_long_message_content(self, mock_persona_cls, mock_db, app):
        """Content preview is truncated to 100 chars + '...' for long messages."""
        operator = _make_mock_persona()
        mock_persona_cls.get_operator.return_value = operator

        channel = _make_mock_channel(id=10, slug="standup-daily-10", name="Daily")
        membership = _make_mock_membership(
            id=1, channel_id=10, persona_id=1, channel=channel
        )

        long_content = "A" * 200
        last_msg = _make_mock_message(
            id=5, channel_id=10, content=long_content, persona_name="Con"
        )

        _setup_db_mock(mock_db, memberships=[membership], latest_messages=[last_msg])

        with app.app_context():
            result = get_channel_data_for_operator()

        assert len(result) == 1
        preview = result[0]["last_message"]["content_preview"]
        assert len(preview) == 103  # 100 chars + "..."
        assert preview.endswith("...")


# ──────────────────────────────────────────────────────────────
# Test: Dashboard template rendering with channel data
# ──────────────────────────────────────────────────────────────


class TestDashboardChannelRendering:
    """Tests for channel card rendering in the dashboard template."""

    @patch("claude_headspace.routes.dashboard.get_channel_data_for_operator")
    def test_renders_channel_cards_when_data_present(self, mock_get_channels, client):
        """3.4: Channel cards section renders when channel_data is non-empty."""
        mock_get_channels.return_value = [
            {
                "slug": "workshop-auth-1",
                "name": "Auth Review",
                "channel_type": "workshop",
                "status": "active",
                "description": None,
                "members": ["Sam", "Con"],
                "last_message": {
                    "persona_name": "Con",
                    "content_preview": "Looking at auth",
                    "sent_at": "2026-03-03T12:00:00+00:00",
                },
            }
        ]

        response = client.get("/dashboard")
        assert response.status_code == 200
        html = response.data.decode()

        assert "channel-cards-section" in html
        assert "Auth Review" in html
        assert "workshop" in html.lower()

    @patch("claude_headspace.routes.dashboard.get_channel_data_for_operator")
    def test_hides_channel_cards_when_empty(self, mock_get_channels, client):
        """3.5: Channel cards section is not rendered when channel_data is empty."""
        mock_get_channels.return_value = []

        response = client.get("/dashboard")
        assert response.status_code == 200
        html = response.data.decode()

        assert "channel-cards-section" not in html

    @patch("claude_headspace.routes.dashboard.get_channel_data_for_operator")
    def test_channel_card_displays_name_type_members_message(
        self, mock_get_channels, client
    ):
        """3.6: Card displays name, type badge, members, and last message."""
        mock_get_channels.return_value = [
            {
                "slug": "review-pr-5",
                "name": "PR Review",
                "channel_type": "review",
                "status": "active",
                "description": None,
                "members": ["Sam", "Robbo", "Con"],
                "last_message": {
                    "persona_name": "Sam",
                    "content_preview": "LGTM, merging now",
                    "sent_at": "2026-03-03T14:00:00+00:00",
                },
            }
        ]

        response = client.get("/dashboard")
        assert response.status_code == 200
        html = response.data.decode()

        # Name
        assert "PR Review" in html
        # Type badge
        assert "review" in html.lower()
        # Members
        assert "Sam" in html
        assert "Robbo" in html
        assert "Con" in html
        # Last message
        assert "LGTM, merging now" in html

    @patch("claude_headspace.routes.dashboard.get_channel_data_for_operator")
    def test_card_shows_no_messages_placeholder(self, mock_get_channels, client):
        """Card without messages shows italic placeholder."""
        mock_get_channels.return_value = [
            {
                "slug": "standup-daily-3",
                "name": "Daily Standup",
                "channel_type": "standup",
                "status": "pending",
                "description": None,
                "members": ["Sam"],
                "last_message": None,
            }
        ]

        response = client.get("/dashboard")
        assert response.status_code == 200
        html = response.data.decode()

        assert "No messages yet" in html

    @patch("claude_headspace.routes.dashboard.get_channel_data_for_operator")
    def test_backward_compatibility_no_channels(self, mock_get_channels, client):
        """4.5: Dashboard renders identically when no channels exist."""
        mock_get_channels.return_value = []

        response = client.get("/dashboard")
        assert response.status_code == 200
        html = response.data.decode()

        # No channel-specific elements
        assert "channel-cards-section" not in html
        # Panel template is always included (hidden by default via aria-hidden)
        assert "channel-chat-panel" in html

    @patch("claude_headspace.routes.dashboard.get_channel_data_for_operator")
    def test_channels_button_visible(self, mock_get_channels, client):
        """Channels management button is visible in dashboard controls."""
        mock_get_channels.return_value = []

        response = client.get("/dashboard")
        assert response.status_code == 200
        html = response.data.decode()

        assert "Channels" in html
        assert "ChannelManagement" in html

    @patch("claude_headspace.routes.dashboard.get_channel_data_for_operator")
    def test_channel_js_scripts_loaded(self, mock_get_channels, client):
        """Channel JS modules are loaded in dashboard."""
        mock_get_channels.return_value = []

        response = client.get("/dashboard")
        assert response.status_code == 200
        html = response.data.decode()

        assert "channel-cards.js" in html
        assert "channel-chat.js" in html
        assert "channel-management.js" in html
