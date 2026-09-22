"""Tool to list scheduled tasks."""

from pydantic import BaseModel, Field

from ...core.policy import RiskLevel, ToolPolicyMetadata
from ...scheduler.models import TaskFilter, TaskStatus
from ...scheduler.store import Scheduler
from ..base import Tool, ToolContext


class SchedulerListArguments(BaseModel):
    status: TaskStatus | None = Field(default=None, description="Filter by task status")
    name_contains: str | None = Field(
        default=None, max_length=256, description="Filter by name substring"
    )
    limit: int = Field(default=50, ge=1, le=200, description="Maximum results")
    offset: int = Field(default=0, ge=0, description="Pagination offset")


class SchedulerListTool(Tool):
    name = "scheduler.list"
    description = "List scheduled tasks with optional filters"
    arguments_model = SchedulerListArguments
    metadata = ToolPolicyMetadata(risk_level=RiskLevel.NONE, timeout_seconds=10)

    def __init__(self, scheduler: Scheduler) -> None:
        self._scheduler = scheduler

    async def execute(self, arguments: BaseModel, context: ToolContext) -> dict:
        validated = self.arguments_model.model_validate(arguments.model_dump())
        filter = TaskFilter(
            status=validated.status,  # type: ignore[attr-defined]
            name_contains=validated.name_contains,  # type: ignore[attr-defined]
            limit=validated.limit,  # type: ignore[attr-defined]
            offset=validated.offset,  # type: ignore[attr-defined]
        )
        tasks = await self._scheduler.list_tasks(filter)
        return {
            "tasks": [
                {
                    "id": t.id,
                    "name": t.name,
                    "description": t.description,
                    "status": t.status.value,
                    "schedule_type": t.schedule.type.value,
                    "next_run_at": t.next_run_at.isoformat() if t.next_run_at else None,
                    "run_count": t.run_count,
                    "last_run_at": t.last_run_at.isoformat() if t.last_run_at else None,
                    "last_error": t.last_error,
                }
                for t in tasks
            ],
            "count": len(tasks),
        }
