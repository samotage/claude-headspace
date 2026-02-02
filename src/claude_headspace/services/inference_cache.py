"""In-memory cache for inference results."""

import logging
import threading
import time
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """A cached inference result with expiry."""

    result_text: str
    input_tokens: int
    output_tokens: int
    model: str
    cached_at: float
    ttl_seconds: int

    @property
    def is_expired(self) -> bool:
        return (time.monotonic() - self.cached_at) > self.ttl_seconds


class InferenceCache:
    """Thread-safe in-memory cache keyed by content hash."""

    def __init__(self, config: dict):
        cache_config = config.get("openrouter", {}).get("cache", {})
        self.enabled = cache_config.get("enabled", True)
        self.ttl_seconds = cache_config.get("ttl_seconds", 300)
        self._cache: dict[str, CacheEntry] = {}
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0

    def get(self, input_hash: str) -> CacheEntry | None:
        """Look up a cached result by input hash.

        Returns:
            CacheEntry if found and not expired, None otherwise
        """
        if not self.enabled:
            self._misses += 1
            return None

        with self._lock:
            entry = self._cache.get(input_hash)
            if entry is None:
                self._misses += 1
                return None

            if entry.is_expired:
                del self._cache[input_hash]
                self._misses += 1
                return None

            self._hits += 1
            return entry

    def put(self, input_hash: str, result_text: str, input_tokens: int, output_tokens: int, model: str) -> None:
        """Store a result in the cache."""
        if not self.enabled:
            return

        entry = CacheEntry(
            result_text=result_text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model=model,
            cached_at=time.monotonic(),
            ttl_seconds=self.ttl_seconds,
        )

        with self._lock:
            self._cache[input_hash] = entry

    def clear(self) -> None:
        """Clear all cached entries."""
        with self._lock:
            self._cache.clear()

    def evict_expired(self) -> int:
        """Remove all expired entries. Returns count of evicted entries."""
        with self._lock:
            expired_keys = [k for k, v in self._cache.items() if v.is_expired]
            for key in expired_keys:
                del self._cache[key]
            return len(expired_keys)

    @property
    def stats(self) -> dict:
        """Return cache statistics."""
        with self._lock:
            return {
                "enabled": self.enabled,
                "ttl_seconds": self.ttl_seconds,
                "size": len(self._cache),
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": self._hits / max(self._hits + self._misses, 1),
            }
