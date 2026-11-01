"""Tests for AlterraApplication."""

import pytest

from alterra.agent.model import AgentResponse
from alterra.core.application import AlterraApplication
from alterra.core.config import Settings
from alterra.core.errors import ConfigurationError, AgentError
from alterra.core.messages import AssistantMessage, ToolCall, ToolResult, UserMessage
from alterra.tools.registry import ToolRegistry
from alterra.tools.dispatcher import ToolDispatcher
from alterra.tools.base import Tool, ToolContext
from pydantic import BaseModel


class FakeModel:
    def __init__(self, responses: list[AgentResponse]):
        self._responses = responses
        self._call_count = 0

    async def generate(self, messages, tools):
        response = self._responses[self._call_count]
        self._call_count += 1
        return response


class TestTool(Tool):
    name = "test.echo"
    description = "Echo test"

    class Args(BaseModel):
        text: str

    arguments_model = Args

    async def execute(self, arguments: BaseModel, context: ToolContext) -> str:
        return arguments.text


@pytest.fixture
def application() -> AlterraApplication:
    registry = ToolRegistry()
    registry.register(TestTool())
    model = FakeModel([
        AgentResponse(message=AssistantMessage(content="hello")),
    ])
    from alterra.agent.runtime import AgentRuntime
    agent = AgentRuntime(model, registry)
    dispatcher = ToolDispatcher(registry)
    return AlterraApplication(agent, registry, dispatcher)


async def test_end_to_end_simple_response(application: AlterraApplication) -> None:
    reply = await application.handle_message(UserMessage(content="Hi", session_id="test"))
    assert reply.content == "hello"


async def test_session_retains_interaction_history(application: AlterraApplication) -> None:
    await application.handle_message(UserMessage(content="Echo hello", session_id="same"))
    session = application.session("same")
    assert len(session.messages) == 2  # user + assistant


async def test_application_routes_tool_calls() -> None:
    # First response: tool call
    # Second response: final answer
    model = FakeModel([
        AgentResponse(tool_calls=[ToolCall(name="test.echo", arguments={"text": "hi"})]),
        AgentResponse(message=AssistantMessage(content="Tool said: hi")),
    ])
    from alterra.agent.runtime import AgentRuntime
    registry = ToolRegistry()
    registry.register(TestTool())
    agent = AgentRuntime(model, registry)
    dispatcher = ToolDispatcher(registry)
    app = AlterraApplication(agent, registry, dispatcher)

    reply = await app.handle_message(UserMessage(content="Say hi", session_id="test2"))
    assert reply.content == "Tool said: hi"
    session = app.session("test2")
    assert len(session.messages) == 4  # user, tool_call, tool_result, assistant


async def test_application_handles_unknown_tool() -> None:
    # Unknown tool returns error in ToolResult, then model generates fallback
    model = FakeModel([
        AgentResponse(tool_calls=[ToolCall(name="unknown.tool", arguments={})]),
        AgentResponse(message=AssistantMessage(content="I couldn't find that tool")),
    ])
    from alterra.agent.runtime import AgentRuntime
    registry = ToolRegistry()
    agent = AgentRuntime(model, registry)
    dispatcher = ToolDispatcher(registry)
    app = AlterraApplication(agent, registry, dispatcher)

    reply = await app.handle_message(UserMessage(content="test", session_id="test3"))
    assert "couldn't find" in reply.content.lower() or "not available" in reply.content.lower()


async def test_application_tool_round_limit() -> None:
    # Model keeps returning tool calls, should hit limit
    model = FakeModel([
        AgentResponse(tool_calls=[ToolCall(name="test.echo", arguments={"text": "x"})])
        for _ in range(10)
    ])
    from alterra.agent.runtime import AgentRuntime
    registry = ToolRegistry()
    registry.register(TestTool())
    agent = AgentRuntime(model, registry)
    dispatcher = ToolDispatcher(registry)
    app = AlterraApplication(agent, registry, dispatcher, max_tool_rounds=3)

    with pytest.raises(AgentError, match="Tool round limit"):
        await app.handle_message(UserMessage(content="test", session_id="test4"))


def test_openrouter_profile_requires_a_key() -> None:
    # Config validation happens at application initialization, not in Settings
    # Settings allows None for optional fields
    settings = Settings(openrouter_api_key=None)
    assert settings.openrouter_api_key is None

    # The actual validation is in Application.initialize()
    from alterra.app import Application
    app = Application(settings)
    import asyncio
    with pytest.raises(ConfigurationError, match="ALTERRA_OPENROUTER_API_KEY"):
        asyncio.run(app.initialize())