from __future__ import annotations

import time
from typing import Any

_TTLStore = dict[str, tuple[float, Any]]


class TTLCache:
    def __init__(self, ttl_seconds: int) -> None:
        self._ttl = ttl_seconds
        self._store: _TTLStore = {}

    def get(self, key: str) -> Any | None:
        item = self._store.get(key)
        if not item:
            return None
        ts, value = item
        if time.time() - ts <= self._ttl:
            return value
        self._store.pop(key, None)
        return None

    def set(self, key: str, value: Any) -> None:
        self._store[key] = (time.time(), value)

    def clear(self) -> None:
        self._store.clear()
