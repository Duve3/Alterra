"""Tool to delete a memory record."""

from pydantic import BaseModel, Field

from ...core.errors import ToolError
from ...core.policy import RiskLevel, ToolPolicyMetadata
from ...memory.store import MemoryStore
from ..base import Tool, ToolContext


class MemoryDeleteArguments(BaseModel):
    memory_id: str = Field(min_length=1, description="The ID of the memory to delete.")


class MemoryDeleteTool(Tool):
    name = "memory.delete"
    description = "Permanently delete a stored memory by its ID."
    arguments_model = MemoryDeleteArguments
    metadata = ToolPolicyMetadata(
        risk_level=RiskLevel.MEDIUM, requires_confirmation=True, timeout_seconds=10
    )

    def __init__(self, memory_store: MemoryStore) -> None:
        self._store = memory_store

    async def execute(self, arguments: BaseModel, context: ToolContext) -> dict:
        validated = self.arguments_model.model_validate(arguments.model_dump())
        deleted = await self._store.delete(validated.memory_id)  # type: ignore[attr-defined]
        if not deleted:
            raise ToolError(f"Memory not found: {validated.memory_id}")  # type: ignore[attr-defined]
        return {"success": True, "id": validated.memory_id}  # type: ignore[attr-defined]
