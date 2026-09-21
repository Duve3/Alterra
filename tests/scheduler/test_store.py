"""Tests for scheduler store and scheduler."""

import pytest

from alterra.scheduler import SQLiteTaskStore, TaskFilter
from alterra.scheduler.models import Schedule, ScheduleType, TaskCreate, TaskStatus


@pytest.fixture
def database_path(tmp_path):
    return tmp_path / "tasks.db"


async def test_store_persists_task(database_path) -> None:
    store = SQLiteTaskStore(database_path)
    schedule = Schedule(type=ScheduleType.ONCE, run_at="2025-01-01T12:00:00+00:00")
    task = TaskCreate(
        name="test", schedule=schedule, tool_name="echo.repeat", tool_arguments={"text": "hi"}
    )

    created = await store.create(task)
    assert created.id is not None
    assert created.name == "test"
    assert created.status == TaskStatus.PENDING

    retrieved = await store.get(created.id)
    assert retrieved is not None
    assert retrieved.name == "test"
    assert retrieved.tool_name == "echo.repeat"


async def test_store_update_task(database_path) -> None:
    store = SQLiteTaskStore(database_path)
    schedule = Schedule(type=ScheduleType.ONCE, run_at="2025-01-01T12:00:00+00:00")
    task = await store.create(
        TaskCreate(name="test", schedule=schedule, tool_name="x", tool_arguments={})
    )

    task.status = TaskStatus.RUNNING
    updated = await store.update(task)
    assert updated.status == TaskStatus.RUNNING

    retrieved = await store.get(task.id)
    assert retrieved.status == TaskStatus.RUNNING


async def test_store_delete_task(database_path) -> None:
    store = SQLiteTaskStore(database_path)
    schedule = Schedule(type=ScheduleType.ONCE, run_at="2025-01-01T12:00:00+00:00")
    task = await store.create(
        TaskCreate(name="test", schedule=schedule, tool_name="x", tool_arguments={})
    )

    deleted = await store.delete(task.id)
    assert deleted is True

    retrieved = await store.get(task.id)
    assert retrieved is None

    deleted_again = await store.delete(task.id)
    assert deleted_again is False


async def test_store_list_tasks(database_path) -> None:
    store = SQLiteTaskStore(database_path)
    schedule = Schedule(type=ScheduleType.ONCE, run_at="2025-01-01T12:00:00+00:00")

    await store.create(
        TaskCreate(name="task one", schedule=schedule, tool_name="x", tool_arguments={})
    )
    await store.create(
        TaskCreate(name="task two", schedule=schedule, tool_name="y", tool_arguments={})
    )
    await store.create(
        TaskCreate(name="other", schedule=schedule, tool_name="z", tool_arguments={})
    )

    all_tasks = await store.list(TaskFilter())
    assert len(all_tasks) == 3

    filtered = await store.list(TaskFilter(name_contains="task"))
    assert len(filtered) == 2
    assert all("task" in t.name for t in filtered)

    limited = await store.list(TaskFilter(limit=1))
    assert len(limited) == 1


async def test_store_get_due_tasks(database_path) -> None:
    store = SQLiteTaskStore(database_path)
    from datetime import UTC, datetime, timedelta
    from alterra.scheduler.models import TaskRecord, TaskStatus

    past = datetime.now(UTC) - timedelta(minutes=1)
    future = datetime.now(UTC) + timedelta(minutes=1)

    # Create tasks with next_run_at set directly (simulating scheduler.create_task)
    due_task = TaskRecord(
        name="due",
        schedule=Schedule(type=ScheduleType.ONCE, run_at=past.isoformat()),
        tool_name="x",
        tool_arguments={},
        next_run_at=past,
    )
    not_due_task = TaskRecord(
        name="not due",
        schedule=Schedule(type=ScheduleType.ONCE, run_at=future.isoformat()),
        tool_name="y",
        tool_arguments={},
        next_run_at=future,
    )

    await store.create(due_task)
    await store.create(not_due_task)

    due = await store.get_due_tasks(datetime.now(UTC))
    assert len(due) == 1
    assert due[0].name == "due"
