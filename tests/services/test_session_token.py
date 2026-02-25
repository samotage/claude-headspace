"""Tests for the session token service."""

import threading

import pytest

from claude_headspace.services.session_token import SessionTokenService, TokenInfo


@pytest.fixture
def service():
    """Create a fresh SessionTokenService."""
    return SessionTokenService()


class TestGenerate:
    """Tests for token generation."""

    def test_generates_unique_tokens(self, service):
        token1 = service.generate(agent_id=1)
        token2 = service.generate(agent_id=2)
        assert token1 != token2
        assert len(token1) > 20  # URL-safe base64 of 32 bytes
        assert len(token2) > 20

    def test_replaces_existing_token_for_same_agent(self, service):
        token1 = service.generate(agent_id=1)
        token2 = service.generate(agent_id=1)

        assert token1 != token2
        assert service.validate(token1) is None  # old token revoked
        assert service.validate(token2) is not None
        assert service.token_count == 1

    def test_stores_feature_flags(self, service):
        flags = {"file_upload": True, "voice_mic": False}
        token = service.generate(agent_id=1, feature_flags=flags)

        info = service.validate(token)
        assert info is not None
        assert info.feature_flags == flags

    def test_default_feature_flags_empty(self, service):
        token = service.generate(agent_id=1)
        info = service.validate(token)
        assert info.feature_flags == {}


class TestValidate:
    """Tests for token validation."""

    def test_valid_token_returns_info(self, service):
        token = service.generate(agent_id=42)
        info = service.validate(token)

        assert info is not None
        assert isinstance(info, TokenInfo)
        assert info.agent_id == 42

    def test_invalid_token_returns_none(self, service):
        assert service.validate("nonexistent-token") is None

    def test_empty_string_returns_none(self, service):
        assert service.validate("") is None


class TestValidateForAgent:
    """Tests for agent-scoped token validation."""

    def test_correct_agent_returns_info(self, service):
        token = service.generate(agent_id=1)
        info = service.validate_for_agent(token, agent_id=1)
        assert info is not None
        assert info.agent_id == 1

    def test_wrong_agent_returns_none(self, service):
        token = service.generate(agent_id=1)
        info = service.validate_for_agent(token, agent_id=2)
        assert info is None

    def test_invalid_token_returns_none(self, service):
        info = service.validate_for_agent("bad-token", agent_id=1)
        assert info is None


class TestRevoke:
    """Tests for token revocation."""

    def test_revoke_existing_token(self, service):
        token = service.generate(agent_id=1)
        assert service.revoke(token) is True
        assert service.validate(token) is None
        assert service.token_count == 0

    def test_revoke_nonexistent_token(self, service):
        assert service.revoke("nonexistent") is False

    def test_revoke_for_agent(self, service):
        token = service.generate(agent_id=1)
        assert service.revoke_for_agent(1) is True
        assert service.validate(token) is None

    def test_revoke_for_agent_nonexistent(self, service):
        assert service.revoke_for_agent(999) is False


class TestGetAgentId:
    """Tests for agent ID lookup."""

    def test_valid_token(self, service):
        token = service.generate(agent_id=7)
        assert service.get_agent_id(token) == 7

    def test_invalid_token(self, service):
        assert service.get_agent_id("bad") is None


class TestGetFeatureFlags:
    """Tests for feature flag lookup."""

    def test_valid_token_with_flags(self, service):
        flags = {"a": True, "b": False}
        token = service.generate(agent_id=1, feature_flags=flags)
        assert service.get_feature_flags(token) == flags

    def test_invalid_token_returns_empty(self, service):
        assert service.get_feature_flags("bad") == {}


class TestTokenCount:
    """Tests for the token_count property."""

    def test_starts_at_zero(self, service):
        assert service.token_count == 0

    def test_counts_active_tokens(self, service):
        service.generate(agent_id=1)
        service.generate(agent_id=2)
        assert service.token_count == 2

    def test_decrements_on_revoke(self, service):
        token = service.generate(agent_id=1)
        service.generate(agent_id=2)
        service.revoke(token)
        assert service.token_count == 1


class TestThreadSafety:
    """Basic thread safety tests."""

    def test_concurrent_generate_and_validate(self, service):
        """Concurrent generation and validation should not crash."""
        errors = []

        def generate_tokens():
            try:
                for i in range(50):
                    service.generate(agent_id=1000 + i)
            except Exception as e:
                errors.append(e)

        def validate_tokens():
            try:
                for _ in range(50):
                    service.validate("nonexistent")
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=generate_tokens),
            threading.Thread(target=validate_tokens),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
