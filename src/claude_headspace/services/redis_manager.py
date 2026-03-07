"""Redis connection manager with graceful degradation.

Centralised Redis connection pool management registered at
app.extensions["redis_manager"]. All Redis keys are namespaced
with a configurable prefix (default "headspace:") to share
Redis instances safely.

When Redis is unavailable, all operations return None/False
gracefully so consuming services can fall back to in-memory state.
"""

import json
import logging
import threading
import time
from typing import Any

logger = logging.getLogger(__name__)


class RedisManager:
    """Thread-safe Redis connection manager with graceful degradation.

    Provides namespaced key operations and health checks. On connection
    failure, sets is_available=False and retries with exponential backoff.
    """

    def __init__(self, config: dict) -> None:
        redis_config = config.get("redis", {})
        self._enabled = redis_config.get("enabled", True)
        self._namespace = redis_config.get("namespace", "headspace:")
        self._retry_interval = redis_config.get("retry_interval", 5)
        self._max_retry_interval = redis_config.get("max_retry_interval", 60)

        self._client = None
        self._is_available = False
        self._last_error: str | None = None
        self._consecutive_failures = 0
        self._last_reconnect_attempt = 0.0
        self._lock = threading.Lock()

        if not self._enabled:
            logger.info("Redis disabled by configuration")
            return

        try:
            import redis

            pool = redis.ConnectionPool(
                host=redis_config.get("host", "localhost"),
                port=redis_config.get("port", 6379),
                password=redis_config.get("password", "") or None,
                db=redis_config.get("db", 0),
                max_connections=redis_config.get("pool_size", 10),
                socket_timeout=redis_config.get("socket_timeout", 2),
                socket_connect_timeout=redis_config.get("socket_connect_timeout", 2),
                decode_responses=True,
            )
            self._client = redis.Redis(connection_pool=pool)

            # Test connection
            self._client.ping()
            self._is_available = True
            logger.info(
                "Redis connected: %s:%s db=%s namespace=%s",
                redis_config.get("host", "localhost"),
                redis_config.get("port", 6379),
                redis_config.get("db", 0),
                self._namespace,
            )
        except ImportError:
            logger.warning("redis package not installed, Redis features disabled")
            self._last_error = "redis package not installed"
        except Exception as e:
            self._last_error = str(e)
            self._is_available = False
            logger.warning(
                "Redis connection failed (will use in-memory fallback): %s", e
            )

    @property
    def is_available(self) -> bool:
        """Whether Redis is currently reachable."""
        return self._is_available

    @property
    def enabled(self) -> bool:
        """Whether Redis is enabled in configuration."""
        return self._enabled

    def key(self, *parts: str) -> str:
        """Build a namespaced Redis key.

        Example: key("cache", "abc123") -> "headspace:cache:abc123"
        """
        return self._namespace + ":".join(parts)

    def _try_reconnect(self) -> bool:
        """Attempt to reconnect with exponential backoff."""
        if not self._enabled or self._client is None:
            return False

        now = time.time()
        backoff = min(
            self._retry_interval * (2**self._consecutive_failures),
            self._max_retry_interval,
        )
        if (now - self._last_reconnect_attempt) < backoff:
            return False

        self._last_reconnect_attempt = now
        try:
            self._client.ping()
            self._is_available = True
            self._consecutive_failures = 0
            self._last_error = None
            logger.info("Redis reconnected successfully")
            return True
        except Exception as e:
            self._consecutive_failures += 1
            self._last_error = str(e)
            return False

    def _handle_error(self, operation: str, e: Exception) -> None:
        """Handle a Redis operation error."""
        self._is_available = False
        self._last_error = str(e)
        self._consecutive_failures += 1
        logger.warning("Redis %s failed (degrading to in-memory): %s", operation, e)

    def _ensure_available(self) -> bool:
        """Check availability, attempting reconnect if needed."""
        if self._is_available:
            return True
        if not self._enabled or self._client is None:
            return False
        return self._try_reconnect()

    # ── Basic Key Operations ─────────────────────────────────────────

    def get(self, key: str) -> str | None:
        """Get a string value by key."""
        if not self._ensure_available():
            return None
        try:
            return self._client.get(key)
        except Exception as e:
            self._handle_error("GET", e)
            return None

    def set(self, key: str, value: str, ex: int | None = None) -> bool:
        """Set a string value with optional expiry in seconds."""
        if not self._ensure_available():
            return False
        try:
            self._client.set(key, value, ex=ex)
            return True
        except Exception as e:
            self._handle_error("SET", e)
            return False

    def set_nx(self, key: str, value: str, ex: int | None = None) -> bool:
        """Set a value only if key doesn't exist. Returns True if set."""
        if not self._ensure_available():
            return False
        try:
            result = self._client.set(key, value, ex=ex, nx=True)
            return result is not None
        except Exception as e:
            self._handle_error("SET NX", e)
            return False

    def delete(self, *keys: str) -> int:
        """Delete one or more keys. Returns count of deleted keys."""
        if not self._ensure_available():
            return 0
        try:
            return self._client.delete(*keys)
        except Exception as e:
            self._handle_error("DELETE", e)
            return 0

    def exists(self, key: str) -> bool:
        """Check if a key exists."""
        if not self._ensure_available():
            return False
        try:
            return bool(self._client.exists(key))
        except Exception as e:
            self._handle_error("EXISTS", e)
            return False

    def expire(self, key: str, seconds: int) -> bool:
        """Set TTL on a key."""
        if not self._ensure_available():
            return False
        try:
            return bool(self._client.expire(key, seconds))
        except Exception as e:
            self._handle_error("EXPIRE", e)
            return False

    def incr(self, key: str) -> int | None:
        """Increment an integer key. Returns new value or None on failure."""
        if not self._ensure_available():
            return None
        try:
            return self._client.incr(key)
        except Exception as e:
            self._handle_error("INCR", e)
            return None

    def ttl(self, key: str) -> int | None:
        """Get the TTL of a key in seconds. Returns None on failure."""
        if not self._ensure_available():
            return None
        try:
            result = self._client.ttl(key)
            return result if result >= 0 else None
        except Exception as e:
            self._handle_error("TTL", e)
            return None

    # ── Hash Operations ──────────────────────────────────────────────

    def hset(self, key: str, field: str, value: str) -> bool:
        """Set a hash field."""
        if not self._ensure_available():
            return False
        try:
            self._client.hset(key, field, value)
            return True
        except Exception as e:
            self._handle_error("HSET", e)
            return False

    def hget(self, key: str, field: str) -> str | None:
        """Get a hash field value."""
        if not self._ensure_available():
            return None
        try:
            return self._client.hget(key, field)
        except Exception as e:
            self._handle_error("HGET", e)
            return None

    def hgetall(self, key: str) -> dict[str, str]:
        """Get all fields in a hash."""
        if not self._ensure_available():
            return {}
        try:
            return self._client.hgetall(key) or {}
        except Exception as e:
            self._handle_error("HGETALL", e)
            return {}

    def hdel(self, key: str, *fields: str) -> int:
        """Delete hash fields. Returns count of deleted fields."""
        if not self._ensure_available():
            return 0
        try:
            return self._client.hdel(key, *fields)
        except Exception as e:
            self._handle_error("HDEL", e)
            return 0

    def hincrby(self, key: str, field: str, amount: int = 1) -> int | None:
        """Increment a hash field by amount. Returns new value or None."""
        if not self._ensure_available():
            return None
        try:
            return self._client.hincrby(key, field, amount)
        except Exception as e:
            self._handle_error("HINCRBY", e)
            return None

    # ── Set Operations ───────────────────────────────────────────────

    def sadd(self, key: str, *members: str) -> int:
        """Add members to a set. Returns count of new members added."""
        if not self._ensure_available():
            return 0
        try:
            return self._client.sadd(key, *members)
        except Exception as e:
            self._handle_error("SADD", e)
            return 0

    def srem(self, key: str, *members: str) -> int:
        """Remove members from a set. Returns count removed."""
        if not self._ensure_available():
            return 0
        try:
            return self._client.srem(key, *members)
        except Exception as e:
            self._handle_error("SREM", e)
            return 0

    def sismember(self, key: str, member: str) -> bool:
        """Check if a member is in a set."""
        if not self._ensure_available():
            return False
        try:
            return bool(self._client.sismember(key, member))
        except Exception as e:
            self._handle_error("SISMEMBER", e)
            return False

    def smembers(self, key: str) -> set[str]:
        """Get all members of a set."""
        if not self._ensure_available():
            return set()
        try:
            return self._client.smembers(key) or set()
        except Exception as e:
            self._handle_error("SMEMBERS", e)
            return set()

    # ── List Operations ──────────────────────────────────────────────

    def lpush(self, key: str, *values: str) -> int:
        """Push values onto the left of a list. Returns list length."""
        if not self._ensure_available():
            return 0
        try:
            return self._client.lpush(key, *values)
        except Exception as e:
            self._handle_error("LPUSH", e)
            return 0

    def rpop(self, key: str) -> str | None:
        """Pop a value from the right of a list."""
        if not self._ensure_available():
            return None
        try:
            return self._client.rpop(key)
        except Exception as e:
            self._handle_error("RPOP", e)
            return None

    def llen(self, key: str) -> int:
        """Get the length of a list."""
        if not self._ensure_available():
            return 0
        try:
            return self._client.llen(key)
        except Exception as e:
            self._handle_error("LLEN", e)
            return 0

    # ── Stream Operations ────────────────────────────────────────────

    def xadd(
        self,
        key: str,
        fields: dict[str, str],
        maxlen: int | None = None,
        approximate: bool = True,
    ) -> str | None:
        """Add an entry to a stream. Returns the entry ID or None."""
        if not self._ensure_available():
            return None
        try:
            return self._client.xadd(
                key, fields, maxlen=maxlen, approximate=approximate
            )
        except Exception as e:
            self._handle_error("XADD", e)
            return None

    def xrange(
        self,
        key: str,
        min: str = "-",
        max: str = "+",
        count: int | None = None,
    ) -> list:
        """Read entries from a stream in range."""
        if not self._ensure_available():
            return []
        try:
            return self._client.xrange(key, min=min, max=max, count=count) or []
        except Exception as e:
            self._handle_error("XRANGE", e)
            return []

    def xlen(self, key: str) -> int:
        """Get the length of a stream."""
        if not self._ensure_available():
            return 0
        try:
            return self._client.xlen(key)
        except Exception as e:
            self._handle_error("XLEN", e)
            return 0

    def xtrim(self, key: str, maxlen: int, approximate: bool = True) -> int:
        """Trim a stream to maxlen entries. Returns count of removed entries."""
        if not self._ensure_available():
            return 0
        try:
            return self._client.xtrim(key, maxlen=maxlen, approximate=approximate)
        except Exception as e:
            self._handle_error("XTRIM", e)
            return 0

    # ── JSON Helpers ─────────────────────────────────────────────────

    def get_json(self, key: str) -> Any | None:
        """Get and JSON-decode a value."""
        raw = self.get(key)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return None

    def set_json(self, key: str, value: Any, ex: int | None = None) -> bool:
        """JSON-encode and set a value."""
        try:
            encoded = json.dumps(value, default=str)
        except (TypeError, ValueError):
            return False
        return self.set(key, encoded, ex=ex)

    def hget_json(self, key: str, field: str) -> Any | None:
        """Get and JSON-decode a hash field."""
        raw = self.hget(key, field)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return None

    def hset_json(self, key: str, field: str, value: Any) -> bool:
        """JSON-encode and set a hash field."""
        try:
            encoded = json.dumps(value, default=str)
        except (TypeError, ValueError):
            return False
        return self.hset(key, field, encoded)

    # ── Health & Diagnostics ─────────────────────────────────────────

    def ping(self) -> bool:
        """Test Redis connectivity."""
        if not self._enabled or self._client is None:
            return False
        try:
            self._client.ping()
            self._is_available = True
            self._consecutive_failures = 0
            return True
        except Exception:
            return False

    def get_health_status(self) -> dict[str, Any]:
        """Get Redis health information for the health endpoint."""
        status: dict[str, Any] = {
            "enabled": self._enabled,
            "available": self._is_available,
        }

        if not self._enabled:
            status["status"] = "disabled"
            return status

        if not self._is_available:
            status["status"] = "unavailable"
            status["last_error"] = self._last_error
            status["consecutive_failures"] = self._consecutive_failures
            return status

        status["status"] = "connected"

        # Memory info (optional — may not be available in test environments)
        try:
            info = self._client.info(section="memory")
            status["used_memory_human"] = info.get("used_memory_human", "unknown")
            status["used_memory_bytes"] = info.get("used_memory", 0)
        except Exception:
            status["used_memory_human"] = "unknown"
            status["used_memory_bytes"] = 0

        # Count keys in our namespace (optional)
        try:
            key_count = 0
            cursor = 0
            while True:
                cursor, keys = self._client.scan(
                    cursor=cursor, match=f"{self._namespace}*", count=100
                )
                key_count += len(keys)
                if cursor == 0:
                    break
            status["key_count"] = key_count
        except Exception:
            status["key_count"] = -1

        return status

    def flush_namespace(self) -> int:
        """Delete all keys in our namespace. Returns count deleted. USE WITH CAUTION."""
        if not self._ensure_available():
            return 0
        deleted = 0
        try:
            cursor = 0
            while True:
                cursor, keys = self._client.scan(
                    cursor=cursor, match=f"{self._namespace}*", count=100
                )
                if keys:
                    deleted += self._client.delete(*keys)
                if cursor == 0:
                    break
        except Exception as e:
            self._handle_error("FLUSH_NAMESPACE", e)
        return deleted
