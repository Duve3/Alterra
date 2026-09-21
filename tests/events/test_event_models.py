"""Tests for the event models."""

from alterra.events.models import Event, EventSubscription


def test_event_creation_with_defaults() -> None:
    event = Event(type="test.event", source="test", payload={"key": "value"})
    assert event.type == "test.event"
    assert event.source == "test"
    assert event.payload == {"key": "value"}
    assert event.id is not None
    assert event.timestamp is not None
    assert event.correlation_id is None


def test_event_creation_with_correlation_id() -> None:
    event = Event(type="test.event", source="test", correlation_id="corr-123")
    assert event.correlation_id == "corr-123"


def test_event_subscription_creation() -> None:
    sub = EventSubscription(event_type="test.event", subscriber_id="sub-1")
    assert sub.event_type == "test.event"
    assert sub.subscriber_id == "sub-1"
    assert sub.id is not None
    assert sub.created_at is not None
    assert sub.filter is None


def test_event_subscription_with_filter() -> None:
    sub = EventSubscription(event_type="test.event", subscriber_id="sub-1", filter={"key": "value"})
    assert sub.filter == {"key": "value"}
