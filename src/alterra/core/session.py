"""Temporary conversation state; this is intentionally not long-term memory."""

from __future__ import annotations

from typing import Annotated
from uuid import uuid4

from pydantic import BaseModel, Field

from .messages import AssistantMessage, SystemMessage, ToolResult, UserMessage

ConversationMessage = Annotated[
    UserMessage | AssistantMessage | SystemMessage | ToolResult,
    Field(discriminator="role"),
]


class Session(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    messages: list[ConversationMessage] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)

    def append(self, message: ConversationMessage) -> None:
        self.messages.append(message)
