"""Tests for the channels admin page route."""

import pytest


class TestChannelsPage:
    """Test /channels page serving."""

    def test_channels_page_returns_200(self, client):
        """GET /channels returns 200."""
        resp = client.get("/channels")
        assert resp.status_code == 200

    def test_channels_page_renders_template(self, client):
        """GET /channels renders the channels.html template."""
        resp = client.get("/channels")
        html = resp.data.decode()
        assert "Channels" in html
        assert "channel-admin.js" in html
        assert "channel-filter-tab" in html
