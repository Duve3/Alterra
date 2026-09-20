"""Replaceable persistent-memory storage contract and SQLite implementation."""

from __future__ import annotations

import asyncio
import json
import sqlite3
from pathlib import Path
from typing import Protocol

from .models import MemoryCreate, MemoryRecord, MemoryScope


class MemoryStore(Protocol):
    async def create(self, memory: MemoryCreate) -> MemoryRecord: ...

    async def get(self, memory_id: str) -> MemoryRecord | None: ...

    async def search(
        self,
        query: str,
        *,
        scope: MemoryScope | None = None,
        scope_id: str | None = None,
        limit: int = 10,
    ) -> list[MemoryRecord]: ...

    async def delete(self, memory_id: str) -> bool: ...


class SQLiteMemoryStore:
    """Small local store that opens a short-lived SQLite connection for each operation."""

    def __init__(self, database_path: Path | str) -> None:
        self._database_path = Path(database_path)
        self._initialize_lock = asyncio.Lock()
        self._initialized = False

    async def create(self, memory: MemoryCreate) -> MemoryRecord:
        await self._ensure_initialized()
        record = MemoryRecord(**memory.model_dump())
        await asyncio.to_thread(self._create_sync, record)
        return record

    async def get(self, memory_id: str) -> MemoryRecord | None:
        await self._ensure_initialized()
        row = await asyncio.to_thread(self._get_sync, memory_id)
        return self._record_from_row(row) if row else None

    async def search(
        self,
        query: str,
        *,
        scope: MemoryScope | None = None,
        scope_id: str | None = None,
        limit: int = 10,
    ) -> list[MemoryRecord]:
        if not query.strip():
            return []
        if limit < 1:
            raise ValueError("limit must be at least one")
        await self._ensure_initialized()
        rows = await asyncio.to_thread(self._search_sync, query, scope, scope_id, limit)
        return [self._record_from_row(row) for row in rows]

    async def delete(self, memory_id: str) -> bool:
        await self._ensure_initialized()
        return await asyncio.to_thread(self._delete_sync, memory_id)

    async def _ensure_initialized(self) -> None:
        if self._initialized:
            return
        async with self._initialize_lock:
            if self._initialized:
                return
            await asyncio.to_thread(self._initialize_sync)
            self._initialized = True

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._database_path)

    def _initialize_sync(self) -> None:
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    source TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    scope_id TEXT,
                    confidence REAL NOT NULL,
                    created_by TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute("CREATE INDEX IF NOT EXISTS idx_memories_scope ON memories(scope, scope_id)")

    def _create_sync(self, record: MemoryRecord) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO memories (
                    id, content, source, scope, scope_id, confidence, created_by, metadata_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.id,
                    record.content,
                    record.source.value,
                    record.scope.value,
                    record.scope_id,
                    record.confidence,
                    record.created_by,
                    json.dumps(record.metadata),
                    record.created_at.isoformat(),
                    record.updated_at.isoformat(),
                ),
            )

    def _get_sync(self, memory_id: str) -> sqlite3.Row | None:
        with self._connect() as connection:
            connection.row_factory = sqlite3.Row
            return connection.execute("SELECT * FROM memories WHERE id = ?", (memory_id,)).fetchone()

    def _search_sync(
        self,
        query: str,
        scope: MemoryScope | None,
        scope_id: str | None,
        limit: int,
    ) -> list[sqlite3.Row]:
        clauses = ["LOWER(content) LIKE LOWER(?)"]
        parameters: list[str | int] = [f"%{query}%"]
        if scope is not None:
            clauses.append("scope = ?")
            parameters.append(scope.value)
        if scope_id is not None:
            clauses.append("scope_id = ?")
            parameters.append(scope_id)
        parameters.append(limit)
        with self._connect() as connection:
            connection.row_factory = sqlite3.Row
            return connection.execute(
                f"SELECT * FROM memories WHERE {' AND '.join(clauses)} ORDER BY updated_at DESC LIMIT ?",
                parameters,
            ).fetchall()

    def _delete_sync(self, memory_id: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
            return cursor.rowcount > 0

    @staticmethod
    def _record_from_row(row: sqlite3.Row) -> MemoryRecord:
        return MemoryRecord(
            id=row["id"],
            content=row["content"],
            source=row["source"],
            scope=row["scope"],
            scope_id=row["scope_id"],
            confidence=row["confidence"],
            created_by=row["created_by"],
            metadata=json.loads(row["metadata_json"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
