"""Tool to retrieve memory records."""

import re

from pydantic import BaseModel, Field

from ...core.policy import RiskLevel, ToolPolicyMetadata
from ...memory.models import MemoryRecord, MemoryScope
from ...memory.store import MemoryStore
from ..base import Tool, ToolContext


_LIKE_SPECIAL_CHARS = re.compile(r"[%_?]")


def _sanitize_like_query(query: str) -> str:
    """Remove SQL LIKE special characters that would be treated as literals."""
    return _LIKE_SPECIAL_CHARS.sub("", query)


class MemoryRetrieveArguments(BaseModel):
    query: str = Field(
        default="", description="Search query to find relevant memories. Empty returns all."
    )
    scope: MemoryScope | None = Field(default=None, description="Filter by memory scope.")
    scope_id: str | None = Field(
        default=None, max_length=256, description="Filter by scope identifier."
    )
    limit: int = Field(default=10, ge=1, le=50, description="Maximum number of results.")


class MemoryRetrieveTool(Tool):
    name = "memory.retrieve"
    description = (
        "Search and retrieve stored memories by query. Empty query returns all memories in scope."
    )
    arguments_model = MemoryRetrieveArguments
    metadata = ToolPolicyMetadata(risk_level=RiskLevel.NONE, timeout_seconds=10)

    def __init__(self, memory_store: MemoryStore) -> None:
        self._store = memory_store

    async def execute(self, arguments: MemoryRetrieveArguments, context: ToolContext) -> dict:
        sanitized_query = _sanitize_like_query(arguments.query)
        records = await self._store.search(
            query=sanitized_query,
            scope=arguments.scope,
            scope_id=arguments.scope_id,
            limit=arguments.limit,
        )
        return {
            "results": [
                {
                    "id": r.id,
                    "content": r.content,
                    "source": r.source.value,
                    "scope": r.scope.value,
                    "scope_id": r.scope_id,
                    "confidence": r.confidence,
                    "created_by": r.created_by,
                    "created_at": r.created_at.isoformat(),
                    "updated_at": r.updated_at.isoformat(),
                }
                for r in records
            ],
            "count": len(records),
        }
