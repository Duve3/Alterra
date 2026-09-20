"""Offline deterministic development provider, useful for tests and the initial CLI."""

from __future__ import annotations

import re

from ...core.messages import AssistantMessage, ToolCall, ToolResult, UserMessage
from ...core.session import ConversationMessage
from ..model import AgentResponse


class LocalModel:
    async def generate(self, messages: list[ConversationMessage], tools: list[dict]) -> AgentResponse:
        last = messages[-1]
        if isinstance(last, ToolResult):
            if not last.success:
                return AgentResponse(message=AssistantMessage(content=f"I couldn't complete that: {last.error}"))
            if last.name == "time.current":
                return AgentResponse(message=AssistantMessage(content=str(last.data["iso"])))
            return AgentResponse(message=AssistantMessage(content=str(last.data)))
        if not isinstance(last, UserMessage):
            return AgentResponse(message=AssistantMessage(content="How can I help?"))
        text = last.content.strip()
        echo = re.fullmatch(r"echo\s+[\"']?(.*?)[\"']?", text, flags=re.IGNORECASE)
        if echo:
            return AgentResponse(tool_calls=[ToolCall(name="echo.repeat", arguments={"text": echo.group(1)})])
        if re.search(r"\b(time|clock)\b", text, flags=re.IGNORECASE):
            timezone = "UTC"
            zone = re.search(r"\b(?:in|for)\s+([A-Za-z_]+/[A-Za-z_]+)\b", text)
            if zone:
                timezone = zone.group(1)
            return AgentResponse(tool_calls=[ToolCall(name="time.current", arguments={"timezone": timezone})])
        expression = re.search(r"(?:what is|calculate|compute)\s+([-+*/%().\d\s]+)\??$", text, flags=re.IGNORECASE)
        if expression and re.search(r"\d", expression.group(1)):
            return AgentResponse(tool_calls=[ToolCall(name="calculator.evaluate", arguments={"expression": expression.group(1).strip()})])
        return AgentResponse(message=AssistantMessage(content="I can calculate arithmetic, tell the time, or echo text in the local profile."))
