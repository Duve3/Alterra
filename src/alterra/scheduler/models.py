"""Provider-neutral scheduler models."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class TaskStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ScheduleType(StrEnum):
    ONCE = "once"
    INTERVAL = "interval"
    CRON = "cron"


class Schedule(BaseModel):
    """Defines when a task should run."""

    model_config = ConfigDict(extra="allow")

    type: ScheduleType
    # For ONCE: run_at (ISO datetime)
    # For INTERVAL: seconds (float), optional start_at
    # For CRON: cron_expression (str), optional timezone
    run_at: str | None = None
    seconds: float | None = None
    cron_expression: str | None = None
    timezone: str = "UTC"
    start_at: str | None = None
    end_at: str | None = None
    max_runs: int | None = None


class TaskCreate(BaseModel):
    """Request to create a scheduled task."""

    model_config = ConfigDict(extra="allow")

    name: str = Field(min_length=1, max_length=256)
    description: str = Field(default="", max_length=2048)
    schedule: Schedule
    tool_name: str = Field(min_length=1, description="Tool to invoke when task runs")
    tool_arguments: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class TaskRecord(TaskCreate):
    """Stored task record with runtime state."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_run_at: datetime | None = None
    next_run_at: datetime | None = None
    run_count: int = 0
    last_error: str | None = None


class TaskFilter(BaseModel):
    """Filter for listing tasks."""

    status: TaskStatus | None = None
    name_contains: str | None = None
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)
