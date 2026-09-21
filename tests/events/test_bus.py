"""Tests for the EventBus."""

import asyncio

import pytest

from alterra.events import EventBus
from alterra.events.models import Event


@pytest.fixture
def bus() -> EventBus:
    return EventBus()


@pytest.fixture
def received_events() -> list[Event]:
    return []


async def test_subscribe_and_publish(bus: EventBus, received_events: list[Event]) -> None:
    async def handler(event: Event) -> None:
        received_events.append(event)

    bus.subscribe("test.event", handler, subscriber_id="test-sub")
    await bus.publish(Event(type="test.event", source="test", payload={"data": "hello"}))

    await asyncio.sleep(0.01)  # Allow async handlers to complete
    assert len(received_events) == 1
    assert received_events[0].type == "test.event"
    assert received_events[0].payload == {"data": "hello"}


async def test_multiple_subscribers(bus: EventBus) -> None:
    received: list[Event] = []

    async def handler1(event: Event) -> None:
        received.append(event)

    async def handler2(event: Event) -> None:
        received.append(event)

    bus.subscribe("multi.event", handler1, subscriber_id="sub-1")
    bus.subscribe("multi.event", handler2, subscriber_id="sub-2")
    await bus.publish(Event(type="multi.event", source="test"))

    await asyncio.sleep(0.01)
    assert len(received) == 2


async def test_publish_to_no_subscribers(bus: EventBus) -> None:
    # Should not raise
    await bus.publish(Event(type="no.subscribers", source="test"))


async def test_unsubscribe(bus: EventBus, received_events: list[Event]) -> None:
    async def handler(event: Event) -> None:
        received_events.append(event)

    sub = bus.subscribe("unsub.event", handler, subscriber_id="test-sub")
    await bus.publish(Event(type="unsub.event", source="test"))
    await asyncio.sleep(0.01)
    assert len(received_events) == 1

    bus.unsubscribe(sub.id)
    await bus.publish(Event(type="unsub.event", source="test"))
    await asyncio.sleep(0.01)
    assert len(received_events) == 1  # No new events


async def test_unsubscribe_nonexistent(bus: EventBus) -> None:
    assert bus.unsubscribe("nonexistent-id") is False


async def test_get_subscriptions(bus: EventBus) -> None:
    async def noop(event: Event) -> None:
        pass

    bus.subscribe("type.a", noop, subscriber_id="sub-1")
    bus.subscribe("type.a", noop, subscriber_id="sub-2")
    bus.subscribe("type.b", noop, subscriber_id="sub-3")

    all_subs = bus.get_subscriptions()
    assert len(all_subs) == 3

    type_a_subs = bus.get_subscriptions("type.a")
    assert len(type_a_subs) == 2

    type_b_subs = bus.get_subscriptions("type.b")
    assert len(type_b_subs) == 1

    empty_subs = bus.get_subscriptions("type.c")
    assert len(empty_subs) == 0


async def test_publish_exception_in_handler_does_not_break_others(bus: EventBus) -> None:
    received: list[Event] = []

    async def good_handler(event: Event) -> None:
        received.append(event)

    async def bad_handler(event: Event) -> None:
        raise ValueError("handler error")

    bus.subscribe("error.event", good_handler, subscriber_id="good")
    bus.subscribe("error.event", bad_handler, subscriber_id="bad")

    await bus.publish(Event(type="error.event", source="test"))
    await asyncio.sleep(0.01)

    # Good handler should still have been called
    assert len(received) == 1


async def test_handler_receives_correct_event_data(bus: EventBus) -> None:
    captured: dict = {}

    async def handler(event: Event) -> None:
        captured["event"] = event

    bus.subscribe("data.event", handler, subscriber_id="test")
    test_payload = {"key": "value", "number": 42}
    test_correlation = "corr-123"
    await bus.publish(
        Event(
            type="data.event",
            source="test-source",
            payload=test_payload,
            correlation_id=test_correlation,
        )
    )
    await asyncio.sleep(0.01)

    event = captured["event"]
    assert event.type == "data.event"
    assert event.source == "test-source"
    assert event.payload == test_payload
    assert event.correlation_id == test_correlation
