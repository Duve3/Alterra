"""Event bus for publishing and subscribing to events."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import Awaitable, Callable
from typing import Any

from .models import Event, EventSubscription


class _HandlerEntry:
    """Internal handler entry with metadata for unsubscription."""

    def __init__(self, handler: Callable[[Event], Awaitable[None]], subscriber_id: str) -> None:
        self.handler = handler
        self.subscriber_id = subscriber_id


class EventBus:
    """In-memory event bus with async handler execution."""

    def __init__(self) -> None:
        self._handlers: dict[str, list[_HandlerEntry]] = defaultdict(list)
        self._subscriptions: dict[str, EventSubscription] = {}

    def subscribe(
        self,
        event_type: str,
        handler: Callable[[Event], Awaitable[None]],
        *,
        subscriber_id: str,
        filter: dict[str, Any] | None = None,
    ) -> EventSubscription:
        """Register a handler for an event type."""
        subscription = EventSubscription(
            event_type=event_type,
            subscriber_id=subscriber_id,
            filter=filter,
        )
        self._handlers[event_type].append(_HandlerEntry(handler, subscriber_id))
        self._subscriptions[subscription.id] = subscription
        return subscription

    def unsubscribe(self, subscription_id: str) -> bool:
        """Remove a subscription by its ID."""
        subscription = self._subscriptions.pop(subscription_id, None)
        if subscription is None:
            return False
        handlers = self._handlers.get(subscription.event_type, [])
        self._handlers[subscription.event_type] = [
            h for h in handlers if h.subscriber_id != subscription.subscriber_id
        ]
        return True

    async def publish(self, event: Event) -> None:
        """Publish an event to all matching handlers."""
        handlers = self._handlers.get(event.type, [])
        if not handlers:
            return
        await asyncio.gather(*[h.handler(event) for h in handlers], return_exceptions=True)

    def get_subscriptions(self, event_type: str | None = None) -> list[EventSubscription]:
        """Get all subscriptions, optionally filtered by event type."""
        if event_type is None:
            return list(self._subscriptions.values())
        return [s for s in self._subscriptions.values() if s.event_type == event_type]
