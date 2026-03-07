"""Session token service for remote agent authentication.

Generates, validates, and revokes cryptographically opaque per-agent tokens
using secrets.token_urlsafe(). Tokens are stored in Redis when available,
with in-memory fallback.
"""

import logging
import secrets
import threading
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Token length in bytes (32 bytes = 43 URL-safe characters)
_TOKEN_BYTES = 32


@dataclass
class TokenInfo:
    """Metadata associated with a session token."""

    agent_id: int
    feature_flags: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"agent_id": self.agent_id, "feature_flags": self.feature_flags}

    @classmethod
    def from_dict(cls, data: dict) -> "TokenInfo":
        return cls(
            agent_id=int(data["agent_id"]),
            feature_flags=data.get("feature_flags", {}),
        )


class SessionTokenService:
    """Session token store for remote agent authentication.

    Thread-safe. Backed by Redis when available, with in-memory fallback.
    """

    def __init__(self, redis_manager=None):
        self._lock = threading.Lock()
        # token -> TokenInfo
        self._tokens: dict[str, TokenInfo] = {}
        # agent_id -> token (reverse index for revocation by agent)
        self._agent_tokens: dict[int, str] = {}
        self._redis = redis_manager

    def _redis_available(self) -> bool:
        return self._redis is not None and self._redis.is_available

    def generate(self, agent_id: int, feature_flags: dict | None = None) -> str:
        """Generate a new session token for an agent."""
        token = secrets.token_urlsafe(_TOKEN_BYTES)
        info = TokenInfo(agent_id=agent_id, feature_flags=dict(feature_flags or {}))

        with self._lock:
            # Revoke existing token for this agent (if any)
            old_token = self._agent_tokens.pop(agent_id, None)
            if old_token:
                self._tokens.pop(old_token, None)

            self._tokens[token] = info
            self._agent_tokens[agent_id] = token

        # Mirror to Redis
        if self._redis_available():
            try:
                tokens_key = self._redis.key("session_tokens")
                agent_key = self._redis.key("agent_token", str(agent_id))
                # Remove old token from Redis
                if old_token:
                    self._redis.hdel(tokens_key, old_token)
                # Store new token
                self._redis.hset_json(tokens_key, token, info.to_dict())
                self._redis.set(agent_key, token)
            except Exception:
                pass

        logger.info(f"Session token generated for agent {agent_id}")
        return token

    def validate(self, token: str) -> TokenInfo | None:
        """Validate a session token."""
        # Try Redis first
        if self._redis_available():
            try:
                data = self._redis.hget_json(self._redis.key("session_tokens"), token)
                if data is not None:
                    return TokenInfo.from_dict(data)
            except Exception:
                pass

        # In-memory fallback
        with self._lock:
            return self._tokens.get(token)

    def validate_for_agent(self, token: str, agent_id: int) -> TokenInfo | None:
        """Validate a session token is valid AND scoped to a specific agent."""
        info = self.validate(token)
        if info and info.agent_id == agent_id:
            return info
        return None

    def revoke(self, token: str) -> bool:
        """Revoke a session token."""
        with self._lock:
            info = self._tokens.pop(token, None)
            if info:
                self._agent_tokens.pop(info.agent_id, None)

        if info and self._redis_available():
            try:
                self._redis.hdel(self._redis.key("session_tokens"), token)
                self._redis.delete(self._redis.key("agent_token", str(info.agent_id)))
            except Exception:
                pass

        if info:
            logger.info(f"Session token revoked for agent {info.agent_id}")
            return True
        return False

    def revoke_for_agent(self, agent_id: int) -> bool:
        """Revoke the session token for a specific agent."""
        with self._lock:
            token = self._agent_tokens.pop(agent_id, None)
            if token:
                self._tokens.pop(token, None)

        if token and self._redis_available():
            try:
                self._redis.hdel(self._redis.key("session_tokens"), token)
                self._redis.delete(self._redis.key("agent_token", str(agent_id)))
            except Exception:
                pass

        if token:
            logger.info(f"Session token revoked for agent {agent_id}")
            return True
        return False

    def get_agent_id(self, token: str) -> int | None:
        """Get the agent ID associated with a token."""
        info = self.validate(token)
        return info.agent_id if info else None

    def get_feature_flags(self, token: str) -> dict:
        """Get the feature flags associated with a token."""
        info = self.validate(token)
        return info.feature_flags if info else {}

    @property
    def token_count(self) -> int:
        """Return the number of active tokens."""
        with self._lock:
            return len(self._tokens)
