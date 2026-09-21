"""Tests for scheduler models."""

import pytest

from alterra.scheduler.models import (
    Schedule,
    ScheduleType,
    TaskCreate,
    TaskFilter,
    TaskRecord,
    TaskStatus,
)


def test_schedule_once() -> None:
    s = Schedule(type=ScheduleType.ONCE, run_at="2025-01-01T12:00:00+00:00")
    assert s.type == ScheduleType.ONCE
    assert s.run_at == "2025-01-01T12:00:00+00:00"
    assert s.seconds is None


def test_schedule_interval() -> None:
    s = Schedule(type=ScheduleType.INTERVAL, seconds=60.0, start_at="2025-01-01T00:00:00+00:00")
    assert s.type == ScheduleType.INTERVAL
    assert s.seconds == 60.0
    assert s.start_at == "2025-01-01T00:00:00+00:00"


def test_schedule_cron() -> None:
    s = Schedule(
        type=ScheduleType.CRON, cron_expression="0 * * * *", timezone="America/Los_Angeles"
    )
    assert s.type == ScheduleType.CRON
    assert s.cron_expression == "0 * * * *"
    assert s.timezone == "America/Los_Angeles"


def test_task_create_valid() -> None:
    schedule = Schedule(type=ScheduleType.ONCE, run_at="2025-01-01T12:00:00+00:00")
    task = TaskCreate(
        name="test", schedule=schedule, tool_name="echo.repeat", tool_arguments={"text": "hi"}
    )
    assert task.name == "test"
    assert task.tool_name == "echo.repeat"
    assert task.tool_arguments == {"text": "hi"}


def test_task_create_empty_name_rejected() -> None:
    schedule = Schedule(type=ScheduleType.ONCE, run_at="2025-01-01T12:00:00+00:00")
    with pytest.raises(ValueError):
        TaskCreate(name="", schedule=schedule, tool_name="x", tool_arguments={})


def test_task_filter_defaults() -> None:
    f = TaskFilter()
    assert f.limit == 50
    assert f.offset == 0
    assert f.status is None
    assert f.name_contains is None


def test_task_filter_limits() -> None:
    with pytest.raises(ValueError):
        TaskFilter(limit=0)
    with pytest.raises(ValueError):
        TaskFilter(limit=201)
    with pytest.raises(ValueError):
        TaskFilter(offset=-1)
