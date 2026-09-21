#!/usr/bin/env python
"""Example: Scheduler demo showing one-time and recurring tasks.

This demonstrates the Alterra scheduler subsystem with the scheduler tools.
In a real application, the scheduler would run continuously in the background.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from alterra.core.config import Settings
from alterra.core.messages import ToolCall
from alterra.scheduler import Scheduler, SQLiteTaskStore
from alterra.tools.builtin import SchedulerCancelTool, SchedulerCreateTool, SchedulerListTool
from alterra.tools.dispatcher import ToolDispatcher
from alterra.tools.registry import ToolRegistry


def _future_iso(minutes: int = 1) -> str:
    return (datetime.now(UTC) + timedelta(minutes=minutes)).isoformat()


async def demo_scheduler() -> None:
    """Run a scheduler demo with one-time and interval tasks."""
    print("=== Scheduler Demo ===\n")

    # Setup
    store = SQLiteTaskStore("data/demo_tasks.db")
    executed_tasks: list[str] = []

    async def mock_executor(tool_name: str, arguments: dict) -> None:
        """Mock tool executor that records executions."""
        executed_tasks.append(f"{tool_name}({arguments})")
        print(f"  [EXECUTOR] Ran {tool_name} with {arguments}")

    scheduler = Scheduler(store, mock_executor, tick_interval=0.5)
    registry = ToolRegistry()
    registry.register(SchedulerCreateTool(scheduler))
    registry.register(SchedulerCancelTool(scheduler))
    registry.register(SchedulerListTool(scheduler))
    dispatcher = ToolDispatcher(registry)

    # Start scheduler
    await scheduler.start()
    print("Scheduler started (tick interval: 0.5s)\n")

    try:
        # Create a one-time task
        print("--- Creating one-time task (runs in ~10 seconds) ---")
        result = await dispatcher.dispatch(
            ToolCall(
                name="scheduler.create",
                arguments={
                    "name": "greeting",
                    "description": "Say hello once",
                    "schedule": {"type": "once", "run_at": _future_iso(1)},
                    "tool_name": "echo.repeat",
                    "tool_arguments": {"text": "Hello from scheduler!"},
                },
            ),
            session_id="demo",
        )
        print(f"Created: {result.data}")

        # Create an interval task
        print("\n--- Creating interval task (every 2 seconds, max 3 runs) ---")
        result = await dispatcher.dispatch(
            ToolCall(
                name="scheduler.create",
                arguments={
                    "name": "heartbeat",
                    "description": "Periodic heartbeat",
                    "schedule": {
                        "type": "interval",
                        "seconds": 2,
                        "start_at": _future_iso(0),
                        "max_runs": 3,
                    },
                    "tool_name": "echo.repeat",
                    "tool_arguments": {"text": "heartbeat"},
                },
            ),
            session_id="demo",
        )
        print(f"Created: {result.data}")

        # List tasks
        print("\n--- Listing tasks ---")
        result = await dispatcher.dispatch(
            ToolCall(name="scheduler.list", arguments={"limit": 10}),
            session_id="demo",
        )
        for task in result.data["tasks"]:
            print(f"  {task['name']} ({task['status']}) - next: {task['next_run_at']}")

        # Wait for tasks to execute
        print("\n--- Waiting for tasks to execute (5 seconds) ---")
        await asyncio.sleep(5)

        # List tasks again to see status
        print("\n--- Tasks after execution ---")
        result = await dispatcher.dispatch(
            ToolCall(name="scheduler.list", arguments={"limit": 10}),
            session_id="demo",
        )
        for task in result.data["tasks"]:
            print(f"  {task['name']} ({task['status']}) - runs: {task['run_count']}")

        # Cancel a task (if any pending)
        print("\n--- Cancelling a task ---")
        result = await dispatcher.dispatch(
            ToolCall(name="scheduler.list", arguments={"limit": 10}),
            session_id="demo",
        )
        for task in result.data["tasks"]:
            if task["status"] == "pending":
                cancel_result = await dispatcher.dispatch(
                    ToolCall(name="scheduler.cancel", arguments={"task_id": task["id"]}),
                    session_id="demo",
                )
                print(f"Cancelled {task['name']}: {cancel_result.data}")

        # Show executed tasks
        print("\n--- Executed tasks log ---")
        for exec_task in executed_tasks:
            print(f"  {exec_task}")

    finally:
        await scheduler.stop()
        print("\nScheduler stopped.")

    print("\n=== Demo complete ===")


if __name__ == "__main__":
    asyncio.run(demo_scheduler())
