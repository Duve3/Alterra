"""Scheduler implementation with async execution."""

from __future__ import annotations

import asyncio
import json
import sqlite3
from collections.abc import Callable
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Protocol

from .models import Schedule, ScheduleType, TaskCreate, TaskFilter, TaskRecord, TaskStatus


class TaskStore(Protocol):
    async def create(self, task: TaskRecord) -> TaskRecord: ...
    async def get(self, task_id: str) -> TaskRecord | None: ...
    async def update(self, task: TaskRecord) -> TaskRecord: ...
    async def delete(self, task_id: str) -> bool: ...
    async def list(self, filter: TaskFilter) -> list[TaskRecord]: ...
    async def get_due_tasks(self, now: datetime) -> list[TaskRecord]: ...


class SQLiteTaskStore:
    """SQLite-backed task store."""

    def __init__(self, database_path: Path | str) -> None:
        self._database_path = Path(database_path)
        self._initialize_lock = asyncio.Lock()
        self._initialized = False

    async def _ensure_initialized(self) -> None:
        if self._initialized:
            return
        async with self._initialize_lock:
            if self._initialized:
                return
            await asyncio.to_thread(self._initialize_sync)
            self._initialized = True

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._database_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _initialize_sync(self) -> None:
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as conn, conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT NOT NULL,
                    schedule_json TEXT NOT NULL,
                    tool_name TEXT NOT NULL,
                    tool_arguments_json TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    last_run_at TEXT,
                    next_run_at TEXT,
                    run_count INTEGER NOT NULL DEFAULT 0,
                    last_error TEXT
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_next_run ON tasks(next_run_at)")

    @staticmethod
    def _schedule_to_json(schedule: Schedule) -> str:
        return schedule.model_dump_json()

    @staticmethod
    def _json_to_schedule(data: str) -> Schedule:
        return Schedule.model_validate_json(data)

    @staticmethod
    def _row_to_task(row: sqlite3.Row) -> TaskRecord:
        return TaskRecord(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            schedule=SQLiteTaskStore._json_to_schedule(row["schedule_json"]),
            tool_name=row["tool_name"],
            tool_arguments=json.loads(row["tool_arguments_json"]),
            metadata=json.loads(row["metadata_json"]),
            status=TaskStatus(row["status"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            last_run_at=datetime.fromisoformat(row["last_run_at"]) if row["last_run_at"] else None,
            next_run_at=datetime.fromisoformat(row["next_run_at"]) if row["next_run_at"] else None,
            run_count=row["run_count"],
            last_error=row["last_error"],
        )

    async def create(self, task: TaskCreate | TaskRecord) -> TaskRecord:
        await self._ensure_initialized()
        if isinstance(task, TaskCreate):
            task = TaskRecord(**task.model_dump())
        await asyncio.to_thread(self._create_sync, task)
        return task

    def _create_sync(self, task: TaskRecord) -> None:
        with closing(self._connect()) as conn, conn:
            conn.execute(
                """
                INSERT INTO tasks (
                    id, name, description, schedule_json, tool_name, tool_arguments_json,
                    metadata_json, status, created_at, updated_at, last_run_at, next_run_at,
                    run_count, last_error
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task.id,
                    task.name,
                    task.description,
                    self._schedule_to_json(task.schedule),
                    task.tool_name,
                    json.dumps(task.tool_arguments),
                    json.dumps(task.metadata),
                    task.status.value,
                    task.created_at.isoformat(),
                    task.updated_at.isoformat(),
                    task.last_run_at.isoformat() if task.last_run_at else None,
                    task.next_run_at.isoformat() if task.next_run_at else None,
                    task.run_count,
                    task.last_error,
                ),
            )

    async def get(self, task_id: str) -> TaskRecord | None:
        await self._ensure_initialized()
        return await asyncio.to_thread(self._get_sync, task_id)

    def _get_sync(self, task_id: str) -> TaskRecord | None:
        with closing(self._connect()) as conn, conn:
            row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
            return self._row_to_task(row) if row else None

    async def update(self, task: TaskRecord) -> TaskRecord:
        await self._ensure_initialized()
        task.updated_at = datetime.now(UTC)
        await asyncio.to_thread(self._update_sync, task)
        return task

    def _update_sync(self, task: TaskRecord) -> None:
        with closing(self._connect()) as conn, conn:
            conn.execute(
                """
                UPDATE tasks SET
                    name = ?, description = ?, schedule_json = ?, tool_name = ?,
                    tool_arguments_json = ?, metadata_json = ?, status = ?,
                    updated_at = ?, last_run_at = ?, next_run_at = ?,
                    run_count = ?, last_error = ?
                WHERE id = ?
                """,
                (
                    task.name,
                    task.description,
                    self._schedule_to_json(task.schedule),
                    task.tool_name,
                    json.dumps(task.tool_arguments),
                    json.dumps(task.metadata),
                    task.status.value,
                    task.updated_at.isoformat(),
                    task.last_run_at.isoformat() if task.last_run_at else None,
                    task.next_run_at.isoformat() if task.next_run_at else None,
                    task.run_count,
                    task.last_error,
                    task.id,
                ),
            )

    async def delete(self, task_id: str) -> bool:
        await self._ensure_initialized()
        return await asyncio.to_thread(self._delete_sync, task_id)

    def _delete_sync(self, task_id: str) -> bool:
        with closing(self._connect()) as conn, conn:
            cursor = conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            return cursor.rowcount > 0

    async def list(self, filter: TaskFilter) -> list[TaskRecord]:
        await self._ensure_initialized()
        return await asyncio.to_thread(self._list_sync, filter)

    def _list_sync(self, filter: TaskFilter) -> list[TaskRecord]:
        clauses = []
        params: list[Any] = []
        if filter.status:
            clauses.append("status = ?")
            params.append(filter.status.value)
        if filter.name_contains:
            clauses.append("name LIKE ?")
            params.append(f"%{filter.name_contains}%")
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        params.extend([filter.limit, filter.offset])
        with closing(self._connect()) as conn, conn:
            rows = conn.execute(
                f"SELECT * FROM tasks{where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
                params,
            ).fetchall()
            return [self._row_to_task(row) for row in rows]

    async def get_due_tasks(self, now: datetime) -> list[TaskRecord]:
        await self._ensure_initialized()
        return await asyncio.to_thread(self._get_due_tasks_sync, now)

    def _get_due_tasks_sync(self, now: datetime) -> list[TaskRecord]:
        now_iso = now.isoformat()
        with closing(self._connect()) as conn, conn:
            rows = conn.execute(
                "SELECT * FROM tasks WHERE status = ? AND next_run_at IS NOT NULL AND next_run_at <= ?",
                (TaskStatus.PENDING.value, now_iso),
            ).fetchall()
            return [self._row_to_task(row) for row in rows]


class Scheduler:
    """Async scheduler that executes tasks by invoking tools."""

    def __init__(
        self,
        store: TaskStore,
        tool_executor: Callable[[str, dict[str, Any]], Any],
        *,
        tick_interval: float = 1.0,
    ) -> None:
        self._store = store
        self._execute_tool = tool_executor
        self._tick_interval = tick_interval
        self._running = False
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def create_task(self, create: TaskCreate) -> TaskRecord:
        task = TaskRecord(**create.model_dump())
        task.next_run_at = self._compute_next_run(task.schedule, datetime.now(UTC))
        if task.next_run_at is None:
            task.status = TaskStatus.FAILED
            task.last_error = "Could not compute next run time"
        await self._store.create(task)
        return task

    async def cancel_task(self, task_id: str) -> bool:
        task = await self._store.get(task_id)
        if not task:
            return False
        task.status = TaskStatus.CANCELLED
        await self._store.update(task)
        return True

    async def get_task(self, task_id: str) -> TaskRecord | None:
        return await self._store.get(task_id)

    async def list_tasks(self, filter: TaskFilter) -> list[TaskRecord]:
        return await self._store.list(filter)

    async def _run_loop(self) -> None:
        while self._running:
            try:
                await self._tick()
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001, S110
                # Log in production; swallow to keep scheduler resilient
                pass
            await asyncio.sleep(self._tick_interval)

    async def _tick(self) -> None:
        now = datetime.now(UTC)
        due = await self._store.get_due_tasks(now)
        for task in due:
            await self._execute_task(task, now)

    async def _execute_task(self, task: TaskRecord, now: datetime) -> None:
        task.status = TaskStatus.RUNNING
        task.last_run_at = now
        task.run_count += 1
        await self._store.update(task)

        try:
            await self._execute_tool(task.tool_name, task.tool_arguments)
            task.status = TaskStatus.COMPLETED
            task.last_error = None
        except Exception as e:  # noqa: BLE001
            # Catch all exceptions from tool execution to record failure
            task.status = TaskStatus.FAILED
            task.last_error = str(e)

        # Compute next run
        if task.schedule.type == ScheduleType.ONCE or task.status == TaskStatus.FAILED:
            task.status = (
                TaskStatus.COMPLETED if task.status != TaskStatus.FAILED else TaskStatus.FAILED
            )
            task.next_run_at = None
        else:
            task.next_run_at = self._compute_next_run(task.schedule, now)
            if task.next_run_at is None:
                task.status = TaskStatus.COMPLETED
            elif task.schedule.max_runs and task.run_count >= task.schedule.max_runs:
                task.next_run_at = None
                task.status = TaskStatus.COMPLETED
            else:
                task.status = TaskStatus.PENDING

        await self._store.update(task)

    def _compute_next_run(self, schedule: Schedule, after: datetime) -> datetime | None:
        if schedule.type == ScheduleType.ONCE:
            if schedule.run_at:
                run_at = datetime.fromisoformat(schedule.run_at)
                # If the scheduled time is in the past, run at the next tick (now)
                return max(after, run_at)
            return None

        if schedule.type == ScheduleType.INTERVAL:
            if schedule.seconds is None:
                return None
            if schedule.start_at:
                start = datetime.fromisoformat(schedule.start_at)
                if after < start:
                    return start
                elapsed = (after - start).total_seconds()
                intervals = int(elapsed / schedule.seconds) + 1
                return start + timedelta(seconds=intervals * schedule.seconds)
            return after + timedelta(seconds=schedule.seconds)

        if schedule.type == ScheduleType.CRON:
            # Simplified: not implementing full cron parser here
            return None

        return None
