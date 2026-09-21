"""Provider-neutral event types for the Alterra event system."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class Event(BaseModel):
    """Base event that flows through the event bus."""

    model_config = ConfigDict(extra="allow")

    id: str = Field(default_factory=lambda: str(uuid4()))
    type: str
    source: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    payload: dict[str, Any] = Field(default_factory=dict)
    correlation_id: str | None = None


class EventSubscription(BaseModel):
    """Represents a subscription to an event type."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    event_type: str
    subscriber_id: str
    filter: dict[str, Any] | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
