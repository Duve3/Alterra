#!/usr/bin/env python
"""Example: Periodic event that fires on the 15th minute of each hour.

This demonstrates the Alterra event subsystem with a simple async timer.
In Phase 5 (Scheduler), this would be replaced by the scheduler subsystem.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from alterra.events import EventBus
from alterra.events.models import Event


async def quarter_hour_ticker(bus: EventBus) -> None:
    """Publish a 'time.quarter_hour' event every 15 minutes (at :15, :30, :45, :00)."""
    while True:
        now = datetime.now(UTC)
        # Calculate seconds until next 15-minute boundary
        next_boundary_minute = ((now.minute // 15) + 1) * 15
        if next_boundary_minute == 60:
            next_hour = (now.hour + 1) % 24
            next_boundary = now.replace(hour=next_hour, minute=0, second=0, microsecond=0)
        else:
            next_boundary = now.replace(minute=next_boundary_minute, second=0, microsecond=0)

        wait_seconds = (next_boundary - now).total_seconds()
        print(
            f"[{now.isoformat()}] Waiting {wait_seconds:.0f}s until next quarter hour ({next_boundary.isoformat()})"
        )
        await asyncio.sleep(wait_seconds)

        event = Event(
            type="time.quarter_hour",
            source="scheduler",
            payload={
                "minute": next_boundary.minute,
                "timestamp": next_boundary.isoformat(),
            },
        )
        print(
            f"[{datetime.now(UTC).isoformat()}] Publishing event: {event.type} minute={event.payload['minute']}"
        )
        await bus.publish(event)


async def event_logger(bus: EventBus, ready: asyncio.Event) -> None:
    """Subscribe to all events and log them."""

    async def handler(event: Event) -> None:
        print(f"  [LOGGER] Received: {event.type} from {event.source} payload={event.payload}")

    bus.subscribe("time.quarter_hour", handler, subscriber_id="logger")
    print("[LOGGER] Subscribed to time.quarter_hour")
    ready.set()
    # Keep running until cancelled
    try:
        await asyncio.Event().wait()
    except asyncio.CancelledError:
        pass


async def demo_quarter_hour_events() -> None:
    """Run the demo for a short time to show events firing."""
    bus = EventBus()
    logger_ready = asyncio.Event()

    # Start the logger
    logger_task = asyncio.create_task(event_logger(bus, logger_ready))

    # Wait for logger to be ready
    await logger_ready.wait()

    # Fire one immediately for demo
    print("=== Quarter Hour Event Demo ===")
    print("This would normally wait for real quarter-hour boundaries.")
    print("For demo purposes, we'll fire one event immediately.\n")

    await bus.publish(
        Event(
            type="time.quarter_hour",
            source="scheduler",
            payload={"minute": 15, "timestamp": datetime.now(UTC).isoformat()},
        )
    )

    # Wait for async handlers to complete
    await asyncio.sleep(0.2)

    # Start the ticker (but we'll cancel it after demo)
    ticker_task = asyncio.create_task(quarter_hour_ticker(bus))

    # Give a moment for ticker to print its wait message
    await asyncio.sleep(0.1)

    # Cancel for clean exit
    logger_task.cancel()
    ticker_task.cancel()
    try:
        await logger_task
    except asyncio.CancelledError:
        pass
    try:
        await ticker_task
    except asyncio.CancelledError:
        pass

    print("\n=== Demo complete ===")


if __name__ == "__main__":
    asyncio.run(demo_quarter_hour_events())
