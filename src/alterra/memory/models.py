"""Provider-neutral, intentionally retained memory records."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class MemorySource(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    INTEGRATION = "integration"


class MemoryScope(StrEnum):
    GLOBAL = "global"
    USER = "user"
    SESSION = "session"


class MemoryCreate(BaseModel):
    """A deliberate request to retain a fact; not a conversation transcript item."""

    model_config = ConfigDict(str_strip_whitespace=True)

    content: str = Field(min_length=1, max_length=10_000)
    source: MemorySource = MemorySource.USER
    scope: MemoryScope = MemoryScope.USER
    scope_id: str | None = Field(default=None, max_length=256)
    confidence: float = Field(default=1.0, ge=0, le=1)
    created_by: str = Field(default="user", min_length=1, max_length=256)
    metadata: dict[str, Any] = Field(default_factory=dict)


class MemoryRecord(MemoryCreate):
    id: str = Field(default_factory=lambda: str(uuid4()))
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
