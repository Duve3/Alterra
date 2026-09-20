"""Provider-neutral model interface and response representation."""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, model_validator

from ..core.messages import AssistantMessage, ToolCall
from ..core.session import ConversationMessage


class AgentResponse(BaseModel):
    message: AssistantMessage | None = None
    tool_calls: list[ToolCall] = []

    @model_validator(mode="after")
    def has_one_kind_of_output(self) -> AgentResponse:
        if (self.message is None) == (not self.tool_calls):
            raise ValueError("Agent response must contain exactly a message or one or more tool calls")
        return self


class Model(Protocol):
    async def generate(self, messages: list[ConversationMessage], tools: list[dict]) -> AgentResponse: ...
