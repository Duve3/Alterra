"""Tests for scheduler tools."""

import pytest

from alterra.core.messages import ToolCall
from alterra.core.policy import RiskLevel
from alterra.scheduler import Scheduler, SQLiteTaskStore
from alterra.tools.builtin import SchedulerCancelTool, SchedulerCreateTool, SchedulerListTool
from alterra.tools.dispatcher import ToolDispatcher
from alterra.tools.registry import ToolRegistry


@pytest.fixture
def scheduler(tmp_path) -> Scheduler:
    store = SQLiteTaskStore(tmp_path / "tasks.db")
    return Scheduler(store, lambda name, args: None)


@pytest.fixture
def registry(scheduler: Scheduler) -> ToolRegistry:
    reg = ToolRegistry()
    reg.register(SchedulerCreateTool(scheduler))
    reg.register(SchedulerCancelTool(scheduler))
    reg.register(SchedulerListTool(scheduler))
    return reg


@pytest.fixture
def dispatcher(registry: ToolRegistry) -> ToolDispatcher:
    return ToolDispatcher(registry)


from datetime import UTC, datetime, timedelta


def _future_iso(minutes: int = 10) -> str:
    return (datetime.now(UTC) + timedelta(minutes=minutes)).isoformat()


async def test_scheduler_create_once_task(dispatcher: ToolDispatcher) -> None:
    result = await dispatcher.dispatch(
        ToolCall(
            name="scheduler.create",
            arguments={
                "name": "one-time",
                "description": "Run once",
                "schedule": {"type": "once", "run_at": _future_iso(10)},
                "tool_name": "echo.repeat",
                "tool_arguments": {"text": "Hello!"},
            },
        ),
        session_id="test",
    )
    assert result.success is True
    assert result.data["id"] is not None
    assert result.data["name"] == "one-time"
    assert result.data["status"] == "pending"
    assert result.data["next_run_at"] is not None


async def test_scheduler_create_interval_task(dispatcher: ToolDispatcher) -> None:
    result = await dispatcher.dispatch(
        ToolCall(
            name="scheduler.create",
            arguments={
                "name": "every-minute",
                "schedule": {
                    "type": "interval",
                    "seconds": 60,
                    "start_at": "2025-01-01T00:00:00+00:00",
                },
                "tool_name": "echo.repeat",
                "tool_arguments": {"text": "tick"},
            },
        ),
        session_id="test",
    )
    assert result.success is True
    assert result.data["status"] == "pending"


async def test_scheduler_create_invalid_schedule(dispatcher: ToolDispatcher) -> None:
    result = await dispatcher.dispatch(
        ToolCall(
            name="scheduler.create",
            arguments={
                "name": "bad",
                "schedule": {"type": "interval"},  # missing seconds
                "tool_name": "echo.repeat",
                "tool_arguments": {},
            },
        ),
        session_id="test",
    )
    assert result.success is False


async def test_scheduler_cancel_task(dispatcher: ToolDispatcher) -> None:
    create_result = await dispatcher.dispatch(
        ToolCall(
            name="scheduler.create",
            arguments={
                "name": "to cancel",
                "schedule": {"type": "once", "run_at": _future_iso(10)},
                "tool_name": "echo.repeat",
                "tool_arguments": {"text": "bye"},
            },
        ),
        session_id="test",
    )
    task_id = create_result.data["id"]

    cancel_result = await dispatcher.dispatch(
        ToolCall(name="scheduler.cancel", arguments={"task_id": task_id}),
        session_id="test",
    )
    assert cancel_result.success is True
    assert cancel_result.data["success"] is True


async def test_scheduler_cancel_nonexistent(dispatcher: ToolDispatcher) -> None:
    result = await dispatcher.dispatch(
        ToolCall(name="scheduler.cancel", arguments={"task_id": "nonexistent"}),
        session_id="test",
    )
    assert result.success is False
    assert result.error is not None
    assert "not found" in result.error.lower()


async def test_scheduler_list_tasks(dispatcher: ToolDispatcher) -> None:
    await dispatcher.dispatch(
        ToolCall(
            name="scheduler.create",
            arguments={
                "name": "task alpha",
                "schedule": {"type": "once", "run_at": "2025-12-31T23:59:59+00:00"},
                "tool_name": "echo.repeat",
                "tool_arguments": {"text": "a"},
            },
        ),
        session_id="test",
    )
    await dispatcher.dispatch(
        ToolCall(
            name="scheduler.create",
            arguments={
                "name": "task beta",
                "schedule": {"type": "once", "run_at": "2025-12-31T23:59:59+00:00"},
                "tool_name": "echo.repeat",
                "tool_arguments": {"text": "b"},
            },
        ),
        session_id="test",
    )

    result = await dispatcher.dispatch(
        ToolCall(name="scheduler.list", arguments={"limit": 10}),
        session_id="test",
    )
    assert result.success is True
    assert result.data["count"] == 2
    names = [t["name"] for t in result.data["tasks"]]
    assert "task alpha" in names
    assert "task beta" in names


async def test_scheduler_list_filter_by_name(dispatcher: ToolDispatcher) -> None:
    await dispatcher.dispatch(
        ToolCall(
            name="scheduler.create",
            arguments={
                "name": "prefix task",
                "schedule": {"type": "once", "run_at": "2025-12-31T23:59:59+00:00"},
                "tool_name": "echo.repeat",
                "tool_arguments": {},
            },
        ),
        session_id="test",
    )
    await dispatcher.dispatch(
        ToolCall(
            name="scheduler.create",
            arguments={
                "name": "other task",
                "schedule": {"type": "once", "run_at": "2025-12-31T23:59:59+00:00"},
                "tool_name": "echo.repeat",
                "tool_arguments": {},
            },
        ),
        session_id="test",
    )

    result = await dispatcher.dispatch(
        ToolCall(name="scheduler.list", arguments={"name_contains": "prefix", "limit": 10}),
        session_id="test",
    )
    assert result.success is True
    assert result.data["count"] == 1
    assert result.data["tasks"][0]["name"] == "prefix task"


async def test_scheduler_tool_metadata() -> None:
    from alterra.scheduler import SQLiteTaskStore

    store = SQLiteTaskStore(":memory:")
    scheduler = Scheduler(store, lambda n, a: None)

    create_tool = SchedulerCreateTool(scheduler)
    cancel_tool = SchedulerCancelTool(scheduler)
    list_tool = SchedulerListTool(scheduler)

    assert create_tool.metadata.risk_level == RiskLevel.LOW
    assert cancel_tool.metadata.risk_level == RiskLevel.LOW
    assert list_tool.metadata.risk_level == RiskLevel.NONE
