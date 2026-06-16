"""
TTL in-memory cache.

Caches LLM responses for identical queries (no history).
TTL default: 1 hour. Skip caching when conversation history is present
(responses may differ based on prior context).
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field


@dataclass
class _Entry:
    value: str
    expires_at: float


class TTLCache:
    def __init__(self, default_ttl: int = 3600, max_size: int = 256) -> None:
        self._store: dict[str, _Entry] = {}
        self._default_ttl = default_ttl
        self._max_size = max_size

    def _key(self, query: str) -> str:
        return hashlib.sha256(query.strip().lower().encode()).hexdigest()

    def get(self, query: str) -> str | None:
        key = self._key(query)
        entry = self._store.get(key)
        if entry is None:
            return None
        if time.time() > entry.expires_at:
            del self._store[key]
            return None
        return entry.value

    def set(self, query: str, value: str, ttl: int | None = None) -> None:
        if len(self._store) >= self._max_size:
            # Evict oldest entry
            oldest = min(self._store, key=lambda k: self._store[k].expires_at)
            del self._store[oldest]
        self._store[self._key(query)] = _Entry(
            value=value,
            expires_at=time.time() + (ttl or self._default_ttl),
        )

    def __len__(self) -> int:
        return len(self._store)


# Module-level singleton
cache = TTLCache()
