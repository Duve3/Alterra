"""Tests for AgentRuntime."""

from alterra.agent.model import AgentResponse
from alterra.agent.runtime import AgentRuntime
from alterra.core.messages import AssistantMessage, ToolCall
from alterra.tools.registry import ToolRegistry


class FakeModel:
    def __init__(self, response: AgentResponse):
        self._response = response
        self.captured_tools = None

    async def generate(self, messages, tools):
        self.captured_tools = tools
        return self._response


def test_runtime_passes_tool_definitions_to_model() -> None:
    registry = ToolRegistry()
    model = FakeModel(AgentResponse(message=AssistantMessage(content="ok")))
    runtime = AgentRuntime(model, registry)
    import asyncio
    asyncio.run(runtime.generate([]))
    assert model.captured_tools == []


def test_runtime_returns_model_response() -> None:
    registry = ToolRegistry()
    response = AgentResponse(message=AssistantMessage(content="hello"))
    model = FakeModel(response)
    runtime = AgentRuntime(model, registry)
    import asyncio
    result = asyncio.run(runtime.generate([]))
    assert result.message is not None
    assert result.message.content == "hello"