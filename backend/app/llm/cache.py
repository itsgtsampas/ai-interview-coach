"""Content-hash cache for deterministic calls (temperature 0) and embeddings."""

import hashlib
import threading


def content_hash(*parts: str) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(p.encode("utf-8"))
        h.update(b"\x00")
    return h.hexdigest()


class MemoryCache:
    def __init__(self) -> None:
        self._data: dict[str, str] = {}
        self._lock = threading.Lock()
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> str | None:
        with self._lock:
            v = self._data.get(key)
            if v is None:
                self.misses += 1
            else:
                self.hits += 1
            return v

    def set(self, key: str, value: str) -> None:
        with self._lock:
            self._data[key] = value

    def clear(self) -> None:
        with self._lock:
            self._data.clear()


completion_cache = MemoryCache()
embedding_cache = MemoryCache()
