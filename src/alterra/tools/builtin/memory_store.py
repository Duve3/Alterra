"""Tool to store a memory record."""

from pydantic import BaseModel, Field

from ...core.policy import RiskLevel, ToolPolicyMetadata
from ...memory.models import MemoryCreate, MemoryScope, MemorySource
from ...memory.store import MemoryStore
from ..base import Tool, ToolContext


class MemoryStoreArguments(BaseModel):
    content: str = Field(
        min_length=1, max_length=10_000, description="The fact or information to remember."
    )
    scope: MemoryScope = Field(
        default=MemoryScope.USER, description="Scope of the memory (global, user, session)."
    )
    scope_id: str | None = Field(
        default=None, max_length=256, description="Identifier for the scope (e.g., user ID)."
    )
    confidence: float = Field(
        default=1.0, ge=0, le=1, description="Confidence in this memory (0.0 to 1.0)."
    )
    metadata: dict = Field(default_factory=dict, description="Additional metadata.")


class MemoryStoreTool(Tool):
    name = "memory.store"
    description = "Store a fact or piece of information in long-term memory."
    arguments_model = MemoryStoreArguments
    metadata = ToolPolicyMetadata(risk_level=RiskLevel.LOW, timeout_seconds=10)

    def __init__(self, memory_store: MemoryStore) -> None:
        self._store = memory_store

    async def execute(self, arguments: BaseModel, context: ToolContext) -> dict:
        validated = self.arguments_model.model_validate(arguments.model_dump())
        memory = MemoryCreate(
            content=validated.content,  # type: ignore[attr-defined]
            source=MemorySource.ASSISTANT,
            scope=validated.scope,  # type: ignore[attr-defined]
            scope_id=validated.scope_id,  # type: ignore[attr-defined]
            confidence=validated.confidence,  # type: ignore[attr-defined]
            created_by="assistant",
            metadata=validated.metadata,  # type: ignore[attr-defined]
        )
        record = await self._store.create(memory)
        return {
            "id": record.id,
            "content": record.content,
            "scope": record.scope.value,
            "scope_id": record.scope_id,
            "created_at": record.created_at.isoformat(),
        }
