"""Provider-neutral domain messages used throughout Alterra."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


class Message(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class UserMessage(Message):
    role: Literal["user"] = "user"
    content: str
    session_id: str = "default"


class AssistantMessage(Message):
    role: Literal["assistant"] = "assistant"
    content: str = ""
    tool_calls: list[ToolCall] = Field(default_factory=list)


class SystemMessage(Message):
    role: Literal["system"] = "system"
    content: str


class ToolCall(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class ToolResult(Message):
    role: Literal["tool"] = "tool"
    tool_call_id: str
    name: str
    success: bool
    data: Any = None
    error: str | None = None