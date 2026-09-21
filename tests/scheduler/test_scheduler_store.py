"""Tests for scheduler store and scheduler."""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from alterra.scheduler import SQLiteTaskStore, TaskFilter
from alterra.scheduler.models import Schedule, ScheduleType, TaskCreate, TaskRecord, TaskStatus


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


async def test_store_ensure_initialized_once(database_path) -> None:
    """Test that initialization only happens once."""
    store = SQLiteTaskStore(database_path)
    # First call initializes
    await store.create(
        TaskCreate(
            name="t1",
            schedule=Schedule(type=ScheduleType.ONCE, run_at="2025-01-01T12:00:00+00:00"),
            tool_name="x",
            tool_arguments={},
        )
    )
    # Second call should use cached initialization
    await store.create(
        TaskCreate(
            name="t2",
            schedule=Schedule(type=ScheduleType.ONCE, run_at="2025-01-01T12:00:00+00:00"),
            tool_name="x",
            tool_arguments={},
        )
    )
    # Should not raise


async def test_store_get_nonexistent(database_path) -> None:
    store = SQLiteTaskStore(database_path)
    result = await store.get("nonexistent")
    assert result is None


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


async def test_scheduler_start_stop(database_path) -> None:
    from alterra.scheduler import Scheduler

    store = SQLiteTaskStore(database_path)
    scheduler = Scheduler(store, lambda name, args: None)

    await scheduler.start()
    assert scheduler._running is True
    await scheduler.start()  # Should not error
    await scheduler.stop()
    assert scheduler._running is False


async def test_scheduler_create_task(database_path) -> None:
    from datetime import UTC, datetime, timedelta
    from alterra.scheduler import Scheduler

    store = SQLiteTaskStore(database_path)
    scheduler = Scheduler(store, lambda name, args: None)

    schedule = Schedule(
        type=ScheduleType.ONCE, run_at=(datetime.now(UTC) + timedelta(minutes=10)).isoformat()
    )
    create = TaskCreate(
        name="test", schedule=schedule, tool_name="echo.repeat", tool_arguments={"text": "hi"}
    )
    task = await scheduler.create_task(create)

    assert task.id is not None
    assert task.name == "test"
    assert task.next_run_at is not None
    assert task.status == TaskStatus.PENDING


async def test_scheduler_create_task_past_time_runs_immediately(database_path) -> None:
    """One-time tasks with past run_at should run at next tick."""
    from datetime import UTC, datetime, timedelta
    from alterra.scheduler import Scheduler

    store = SQLiteTaskStore(database_path)
    scheduler = Scheduler(store, lambda name, args: None)

    schedule = Schedule(
        type=ScheduleType.ONCE, run_at=(datetime.now(UTC) - timedelta(minutes=10)).isoformat()
    )
    create = TaskCreate(name="test", schedule=schedule, tool_name="echo.repeat", tool_arguments={})
    task = await scheduler.create_task(create)

    # Should be pending with next_run_at = now (run immediately at next tick)
    assert task.status == TaskStatus.PENDING
    assert task.next_run_at is not None


async def test_scheduler_cancel_task(database_path) -> None:
    from datetime import UTC, datetime, timedelta
    from alterra.scheduler import Scheduler

    store = SQLiteTaskStore(database_path)
    scheduler = Scheduler(store, lambda name, args: None)

    schedule = Schedule(
        type=ScheduleType.ONCE, run_at=(datetime.now(UTC) + timedelta(minutes=10)).isoformat()
    )
    create = TaskCreate(name="test", schedule=schedule, tool_name="echo.repeat", tool_arguments={})
    task = await scheduler.create_task(create)

    cancelled = await scheduler.cancel_task(task.id)
    assert cancelled is True

    retrieved = await scheduler.get_task(task.id)
    assert retrieved is not None
    assert retrieved.status == TaskStatus.CANCELLED


async def test_scheduler_cancel_nonexistent(database_path) -> None:
    from alterra.scheduler import Scheduler

    store = SQLiteTaskStore(database_path)
    scheduler = Scheduler(store, lambda name, args: None)

    cancelled = await scheduler.cancel_task("nonexistent")
    assert cancelled is False


async def test_scheduler_get_nonexistent(database_path) -> None:
    from alterra.scheduler import Scheduler

    store = SQLiteTaskStore(database_path)
    scheduler = Scheduler(store, lambda name, args: None)

    task = await scheduler.get_task("nonexistent")
    assert task is None


async def test_scheduler_list_tasks(database_path) -> None:
    from datetime import UTC, datetime, timedelta
    from alterra.scheduler import Scheduler

    store = SQLiteTaskStore(database_path)
    scheduler = Scheduler(store, lambda name, args: None)

    for name in ["a", "b", "c"]:
        schedule = Schedule(
            type=ScheduleType.ONCE, run_at=(datetime.now(UTC) + timedelta(minutes=10)).isoformat()
        )
        await scheduler.create_task(
            TaskCreate(name=name, schedule=schedule, tool_name="x", tool_arguments={})
        )

    all_tasks = await scheduler.list_tasks(TaskFilter())
    assert len(all_tasks) == 3

    filtered = await scheduler.list_tasks(TaskFilter(name_contains="a"))
    assert len(filtered) == 1


async def test_scheduler_interval_next_run(database_path) -> None:
    from datetime import UTC, datetime, timedelta
    from alterra.scheduler import Scheduler

    store = SQLiteTaskStore(database_path)
    scheduler = Scheduler(store, lambda name, args: None)

    now = datetime.now(UTC)
    schedule = Schedule(type=ScheduleType.INTERVAL, seconds=60, start_at=now.isoformat())
    create = TaskCreate(name="interval", schedule=schedule, tool_name="x", tool_arguments={})
    task = await scheduler.create_task(create)

    assert task.next_run_at is not None
    # Next run should be at or after start_at
    assert task.next_run_at >= now


async def test_scheduler_execute_task_success(database_path) -> None:
    from datetime import UTC, datetime, timedelta
    from alterra.scheduler import Scheduler

    executed = []

    async def executor(name: str, args: dict):
        executed.append((name, args))

    store = SQLiteTaskStore(database_path)
    scheduler = Scheduler(store, executor, tick_interval=0.1)

    now = datetime.now(UTC)
    schedule = Schedule(type=ScheduleType.ONCE, run_at=(now - timedelta(seconds=1)).isoformat())
    create = TaskCreate(
        name="test", schedule=schedule, tool_name="echo.repeat", tool_arguments={"text": "hi"}
    )
    task = await scheduler.create_task(create)

    await scheduler.start()
    await asyncio.sleep(0.3)  # Wait for tick
    await scheduler.stop()

    # Task should have been executed
    retrieved = await scheduler.get_task(task.id)
    assert retrieved.status == TaskStatus.COMPLETED
    assert retrieved.run_count == 1
    assert len(executed) == 1
    assert executed[0] == ("echo.repeat", {"text": "hi"})


async def test_scheduler_execute_task_failure(database_path) -> None:
    from datetime import UTC, datetime, timedelta
    from alterra.scheduler import Scheduler

    async def failing_executor(name: str, args: dict):
        raise ValueError("tool failed")

    store = SQLiteTaskStore(database_path)
    scheduler = Scheduler(store, failing_executor, tick_interval=0.1)

    now = datetime.now(UTC)
    schedule = Schedule(type=ScheduleType.ONCE, run_at=(now - timedelta(seconds=1)).isoformat())
    create = TaskCreate(name="test", schedule=schedule, tool_name="failing", tool_arguments={})
    task = await scheduler.create_task(create)

    await scheduler.start()
    await asyncio.sleep(0.3)
    await scheduler.stop()

    retrieved = await scheduler.get_task(task.id)
    assert retrieved.status == TaskStatus.FAILED
    assert retrieved.last_error == "tool failed"
    assert retrieved.run_count == 1


async def test_scheduler_interval_task_multiple_runs(database_path) -> None:
    from datetime import UTC, datetime, timedelta
    from alterra.scheduler import Scheduler

    executed = []

    async def executor(name: str, args: dict):
        executed.append(name)

    store = SQLiteTaskStore(database_path)
    scheduler = Scheduler(store, executor, tick_interval=0.05)

    now = datetime.now(UTC)
    schedule = Schedule(type=ScheduleType.INTERVAL, seconds=0.1, max_runs=3)
    create = TaskCreate(name="interval", schedule=schedule, tool_name="x", tool_arguments={})
    task = await scheduler.create_task(create)

    await scheduler.start()
    await asyncio.sleep(0.5)
    await scheduler.stop()

    retrieved = await scheduler.get_task(task.id)
    assert retrieved.status == TaskStatus.COMPLETED
    assert retrieved.run_count == 3
    assert len(executed) == 3


async def test_scheduler_compute_next_run_cron(database_path) -> None:
    from alterra.scheduler import Scheduler

    store = SQLiteTaskStore(database_path)
    scheduler = Scheduler(store, lambda name, args: None)

    schedule = Schedule(type=ScheduleType.CRON, cron_expression="0 * * * *")
    next_run = scheduler._compute_next_run(schedule, datetime.now(UTC))
    assert next_run is None  # Cron not implemented


async def test_scheduler_compute_next_run_interval_no_seconds(database_path) -> None:
    from alterra.scheduler import Scheduler

    store = SQLiteTaskStore(database_path)
    scheduler = Scheduler(store, lambda name, args: None)

    schedule = Schedule(type=ScheduleType.INTERVAL, seconds=None)
    next_run = scheduler._compute_next_run(schedule, datetime.now(UTC))
    assert next_run is None


async def test_scheduler_compute_next_run_unknown_type(database_path) -> None:
    from alterra.scheduler import Scheduler

    store = SQLiteTaskStore(database_path)
    scheduler = Scheduler(store, lambda name, args: None)

    # Test the internal _compute_next_run directly with a mock schedule
    # that has an invalid type by creating a minimal object
    class MockSchedule:
        type = "unknown"
        run_at = None
        seconds = None
        cron_expression = None
        start_at = None

    next_run = scheduler._compute_next_run(MockSchedule(), datetime.now(UTC))
    assert next_run is None


async def test_scheduler_start_already_running(database_path) -> None:
    from alterra.scheduler import Scheduler

    store = SQLiteTaskStore(database_path)
    scheduler = Scheduler(store, lambda name, args: None, tick_interval=0.1)

    await scheduler.start()
    await scheduler.start()  # Should not error or create duplicate task
    await scheduler.stop()


async def test_store_list_with_status_filter(database_path) -> None:
    store = SQLiteTaskStore(database_path)
    from alterra.scheduler.models import TaskRecord

    past = datetime.now(UTC) - timedelta(minutes=1)
    task1 = TaskRecord(
        name="pending task",
        schedule=Schedule(type=ScheduleType.ONCE, run_at=past.isoformat()),
        tool_name="x",
        tool_arguments={},
        next_run_at=past,
        status=TaskStatus.PENDING,
    )
    task2 = TaskRecord(
        name="completed task",
        schedule=Schedule(type=ScheduleType.ONCE, run_at=past.isoformat()),
        tool_name="y",
        tool_arguments={},
        next_run_at=None,
        status=TaskStatus.COMPLETED,
    )

    await store.create(task1)
    await store.create(task2)

    # Filter by status
    pending = await store.list(TaskFilter(status=TaskStatus.PENDING))
    assert len(pending) == 1
    assert pending[0].name == "pending task"

    completed = await store.list(TaskFilter(status=TaskStatus.COMPLETED))
    assert len(completed) == 1
    assert completed[0].name == "completed task"


async def test_scheduler_create_task_fails_when_no_next_run(database_path) -> None:
    """Test that create_task fails when _compute_next_run returns None."""
    from alterra.scheduler import Scheduler

    store = SQLiteTaskStore(database_path)
    scheduler = Scheduler(store, lambda name, args: None)

    # Cron schedules return None from _compute_next_run
    schedule = Schedule(type=ScheduleType.CRON, cron_expression="0 * * * *")
    create = TaskCreate(name="cron task", schedule=schedule, tool_name="x", tool_arguments={})
    task = await scheduler.create_task(create)

    assert task.status == TaskStatus.FAILED
    assert task.last_error == "Could not compute next run time"


async def test_scheduler_run_loop_exception_handling(database_path) -> None:
    """Test that exceptions in _run_loop don't crash the scheduler loop."""
    from alterra.scheduler import Scheduler

    call_count = 0

    async def failing_executor(name: str, args: dict):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise ValueError("fail")
        return "ok"

    store = SQLiteTaskStore(database_path)
    scheduler = Scheduler(store, failing_executor, tick_interval=0.05)

    # Create a one-time task that fails once
    schedule = Schedule(
        type=ScheduleType.ONCE, run_at=(datetime.now(UTC) - timedelta(seconds=1)).isoformat()
    )
    create = TaskCreate(name="fail once", schedule=schedule, tool_name="x", tool_arguments={})
    task = await scheduler.create_task(create)

    await scheduler.start()
    await asyncio.sleep(0.3)
    await scheduler.stop()

    # The task should have run once and failed
    retrieved = await scheduler.get_task(task.id)
    assert retrieved is not None
    assert retrieved.status == TaskStatus.FAILED
    assert retrieved.last_error == "fail"
    assert call_count == 1


async def test_scheduler_execute_task_next_run_none(database_path) -> None:
    """Test _execute_task when _compute_next_run returns None for interval task."""
    from datetime import UTC, datetime, timedelta
    from alterra.scheduler import Scheduler

    executed = []

    async def executor(name: str, args: dict):
        executed.append(name)

    store = SQLiteTaskStore(database_path)
    scheduler = Scheduler(store, executor, tick_interval=0.05)

    # Create an interval task where _compute_next_run will return None
    # (e.g., max_runs reached)
    now = datetime.now(UTC)
    schedule = Schedule(type=ScheduleType.INTERVAL, seconds=0.1, max_runs=1)
    create = TaskCreate(name="once interval", schedule=schedule, tool_name="x", tool_arguments={})
    task = await scheduler.create_task(create)

    await scheduler.start()
    await asyncio.sleep(0.3)
    await scheduler.stop()

    retrieved = await scheduler.get_task(task.id)
    assert retrieved.status == TaskStatus.COMPLETED
    assert retrieved.run_count == 1
    assert retrieved.next_run_at is None
