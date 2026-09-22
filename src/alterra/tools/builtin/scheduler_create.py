"""Tool to create a scheduled task."""

from pydantic import BaseModel, Field, model_validator

from ...core.policy import RiskLevel, ToolPolicyMetadata
from ...scheduler.models import Schedule, ScheduleType, TaskCreate
from ...scheduler.store import Scheduler
from ..base import Tool, ToolContext


class ScheduleArguments(BaseModel):
    type: ScheduleType = Field(description="Schedule type: once, interval, or cron")
    run_at: str | None = Field(default=None, description="ISO datetime for one-time tasks")
    seconds: float | None = Field(
        default=None, gt=0, description="Interval in seconds for recurring tasks"
    )
    cron_expression: str | None = Field(default=None, description="Cron expression for cron tasks")
    timezone: str = Field(default="UTC", description="Timezone for cron tasks")
    start_at: str | None = Field(default=None, description="ISO datetime for interval start")
    end_at: str | None = Field(default=None, description="ISO datetime for interval end")
    max_runs: int | None = Field(default=None, ge=1, description="Maximum number of runs")

    @model_validator(mode="after")
    def validate_schedule_fields(self) -> ScheduleArguments:
        if self.type == ScheduleType.ONCE and not self.run_at:
            raise ValueError("run_at is required for 'once' schedules")
        if self.type == ScheduleType.INTERVAL and self.seconds is None:
            raise ValueError("seconds is required for 'interval' schedules")
        if self.type == ScheduleType.CRON and not self.cron_expression:
            raise ValueError("cron_expression is required for 'cron' schedules")
        return self


class SchedulerCreateArguments(BaseModel):
    name: str = Field(min_length=1, max_length=256, description="Task name")
    description: str = Field(default="", max_length=2048, description="Task description")
    schedule: ScheduleArguments = Field(description="When to run the task")
    tool_name: str = Field(min_length=1, description="Name of the tool to invoke")
    tool_arguments: dict = Field(default_factory=dict, description="Arguments to pass to the tool")
    metadata: dict = Field(default_factory=dict, description="Additional metadata")


class SchedulerCreateTool(Tool):
    name = "scheduler.create"
    description = "Create a scheduled task that invokes a tool at specified times"
    arguments_model = SchedulerCreateArguments
    metadata = ToolPolicyMetadata(risk_level=RiskLevel.LOW, timeout_seconds=10)

    def __init__(self, scheduler: Scheduler) -> None:
        self._scheduler = scheduler

    async def execute(self, arguments: BaseModel, context: ToolContext) -> dict:
        validated = self.arguments_model.model_validate(arguments.model_dump())
        schedule = Schedule(
            type=validated.schedule.type,  # type: ignore[attr-defined]
            run_at=validated.schedule.run_at,  # type: ignore[attr-defined]
            seconds=validated.schedule.seconds,  # type: ignore[attr-defined]
            cron_expression=validated.schedule.cron_expression,  # type: ignore[attr-defined]
            timezone=validated.schedule.timezone,  # type: ignore[attr-defined]
            start_at=validated.schedule.start_at,  # type: ignore[attr-defined]
            end_at=validated.schedule.end_at,  # type: ignore[attr-defined]
            max_runs=validated.schedule.max_runs,  # type: ignore[attr-defined]
        )
        create = TaskCreate(
            name=validated.name,  # type: ignore[attr-defined]
            description=validated.description,  # type: ignore[attr-defined]
            schedule=schedule,
            tool_name=validated.tool_name,  # type: ignore[attr-defined]
            tool_arguments=validated.tool_arguments,  # type: ignore[attr-defined]
            metadata=validated.metadata,  # type: ignore[attr-defined]
        )
        task = await self._scheduler.create_task(create)
        return {
            "id": task.id,
            "name": task.name,
            "status": task.status.value,
            "next_run_at": task.next_run_at.isoformat() if task.next_run_at else None,
        }
