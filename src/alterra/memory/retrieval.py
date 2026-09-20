"""Simple retrieval service; future semantic retrieval can replace this implementation."""

from .models import MemoryRecord, MemoryScope
from .store import MemoryStore


class MemoryRetriever:
    def __init__(self, store: MemoryStore) -> None:
        self._store = store

    async def retrieve(
        self,
        query: str,
        *,
        scope: MemoryScope | None = None,
        scope_id: str | None = None,
        limit: int = 10,
    ) -> list[MemoryRecord]:
        return await self._store.search(query, scope=scope, scope_id=scope_id, limit=limit)
