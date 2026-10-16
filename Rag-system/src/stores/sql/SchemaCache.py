import copy
import threading
import time
from typing import Any, Optional, Tuple


class SchemaCache:
    """
    Small in-memory TTL cache for database schemas and the enriched
    schema (with sample values). Keys start with (provider, database_url)
    so a whole database can be invalidated after an Excel ingest.
    """

    def __init__(self):
        self._data = {}
        self._lock = threading.Lock()

    def get(self, key: Tuple, ttl: int) -> Optional[Any]:

        if ttl <= 0:
            return None

        with self._lock:
            entry = self._data.get(key)

        if entry is None:
            return None

        stored_at, value = entry

        if time.monotonic() - stored_at > ttl:
            with self._lock:
                self._data.pop(key, None)
            return None

        return copy.deepcopy(value)

    def set(self, key: Tuple, value: Any) -> None:

        with self._lock:
            self._data[key] = (time.monotonic(), copy.deepcopy(value))

    def invalidate(self, provider: str, database_url: str) -> None:

        with self._lock:
            for key in [
                k for k in self._data
                if k[0] == provider and k[1] == database_url
            ]:
                del self._data[key]


schema_cache = SchemaCache()