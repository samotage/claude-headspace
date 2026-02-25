"""Session token service for remote agent authentication.

Generates, validates, and revokes cryptographically opaque per-agent tokens
using secrets.token_urlsafe(). Tokens are stored in-memory (they do not
need to survive server restarts because remote agents themselves don't
survive restarts).
"""

import logging
import secrets
import threading
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# Token length in bytes (32 bytes = 43 URL-safe characters)
_TOKEN_BYTES = 32


@dataclass
class TokenInfo:
    """Metadata associated with a session token."""

    agent_id: int
    feature_flags: dict = field(default_factory=dict)


class SessionTokenService:
    """In-memory session token store for remote agent authentication.

    Thread-safe: all mutations are protected by a lock.
    """

    def __init__(self):
        self._lock = threading.Lock()
        # token -> TokenInfo
        self._tokens: dict[str, TokenInfo] = {}
        # agent_id -> token (reverse index for revocation by agent)
        self._agent_tokens: dict[int, str] = {}

    def generate(self, agent_id: int, feature_flags: dict | None = None) -> str:
        """Generate a new session token for an agent.

        If a token already exists for this agent, the old one is revoked
        and replaced.

        Args:
            agent_id: The agent this token authenticates.
            feature_flags: Optional dict of feature flags (e.g. file_upload,
                context_usage, voice_mic).

        Returns:
            The generated opaque token string.
        """
        token = secrets.token_urlsafe(_TOKEN_BYTES)
        info = TokenInfo(agent_id=agent_id, feature_flags=feature_flags or {})

        with self._lock:
            # Revoke existing token for this agent (if any)
            old_token = self._agent_tokens.pop(agent_id, None)
            if old_token:
                self._tokens.pop(old_token, None)

            self._tokens[token] = info
            self._agent_tokens[agent_id] = token

        logger.info(f"Session token generated for agent {agent_id}")
        return token

    def validate(self, token: str) -> Optional[TokenInfo]:
        """Validate a session token.

        Args:
            token: The token string to validate.

        Returns:
            TokenInfo if the token is valid, None otherwise.
        """
        with self._lock:
            return self._tokens.get(token)

    def validate_for_agent(self, token: str, agent_id: int) -> Optional[TokenInfo]:
        """Validate a session token is valid AND scoped to a specific agent.

        Args:
            token: The token string to validate.
            agent_id: The expected agent ID.

        Returns:
            TokenInfo if the token is valid and matches the agent, None otherwise.
        """
        info = self.validate(token)
        if info and info.agent_id == agent_id:
            return info
        return None

    def revoke(self, token: str) -> bool:
        """Revoke a session token.

        Args:
            token: The token to revoke.

        Returns:
            True if the token was found and revoked, False if not found.
        """
        with self._lock:
            info = self._tokens.pop(token, None)
            if info:
                self._agent_tokens.pop(info.agent_id, None)
                logger.info(f"Session token revoked for agent {info.agent_id}")
                return True
            return False

    def revoke_for_agent(self, agent_id: int) -> bool:
        """Revoke the session token for a specific agent.

        Args:
            agent_id: The agent whose token should be revoked.

        Returns:
            True if a token was found and revoked, False if not found.
        """
        with self._lock:
            token = self._agent_tokens.pop(agent_id, None)
            if token:
                self._tokens.pop(token, None)
                logger.info(f"Session token revoked for agent {agent_id}")
                return True
            return False

    def get_agent_id(self, token: str) -> Optional[int]:
        """Get the agent ID associated with a token.

        Args:
            token: The token to look up.

        Returns:
            The agent ID, or None if the token is invalid.
        """
        info = self.validate(token)
        return info.agent_id if info else None

    def get_feature_flags(self, token: str) -> dict:
        """Get the feature flags associated with a token.

        Args:
            token: The token to look up.

        Returns:
            Feature flags dict, or empty dict if token is invalid.
        """
        info = self.validate(token)
        return info.feature_flags if info else {}

    @property
    def token_count(self) -> int:
        """Return the number of active tokens."""
        with self._lock:
            return len(self._tokens)
