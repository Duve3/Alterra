"""Tool to cancel a scheduled task."""

from pydantic import BaseModel, Field

from ...core.errors import ToolError
from ...core.policy import RiskLevel, ToolPolicyMetadata
from ...scheduler.store import Scheduler
from ..base import Tool, ToolContext


class SchedulerCancelArguments(BaseModel):
    task_id: str = Field(min_length=1, description="ID of the task to cancel")


class SchedulerCancelTool(Tool):
    name = "scheduler.cancel"
    description = "Cancel a scheduled task by its ID"
    arguments_model = SchedulerCancelArguments
    metadata = ToolPolicyMetadata(risk_level=RiskLevel.LOW, timeout_seconds=10)

    def __init__(self, scheduler: Scheduler) -> None:
        self._scheduler = scheduler

    async def execute(self, arguments: SchedulerCancelArguments, context: ToolContext) -> dict:
        cancelled = await self._scheduler.cancel_task(arguments.task_id)
        if not cancelled:
            raise ToolError(f"Task not found: {arguments.task_id}")
        return {"success": True, "id": arguments.task_id}
