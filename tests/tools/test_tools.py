"""Tests for tool registry and dispatcher."""

import asyncio
import pytest
from pydantic import BaseModel

from alterra.core.errors import ToolNotFoundError
from alterra.core.messages import ToolCall
from alterra.tools.base import Tool, ToolContext
from alterra.tools.dispatcher import ToolDispatcher
from alterra.tools.registry import ToolRegistry


class EmptyArguments(BaseModel):
    pass


class EchoTool(Tool):
    name = "test.echo"
    description = "Echo test tool"

    class Args(BaseModel):
        text: str

    arguments_model = Args

    async def execute(self, arguments: BaseModel, context: ToolContext) -> str:
        return arguments.text


class SlowTool(Tool):
    name = "test.slow"
    description = "Test execution timeout behavior"
    arguments_model = EmptyArguments
    timeout_seconds = 0.01

    async def execute(self, arguments: BaseModel, context: ToolContext) -> str:
        await asyncio.sleep(0.1)
        return "too late"


class FailingTool(Tool):
    name = "test.fail"
    description = "Test error handling"
    arguments_model = EmptyArguments

    async def execute(self, arguments: BaseModel, context: ToolContext) -> str:
        raise ValueError("intentional failure")


@pytest.fixture
def registry() -> ToolRegistry:
    r = ToolRegistry()
    r.register(EchoTool())
    return r


@pytest.fixture
def dispatcher(registry: ToolRegistry) -> ToolDispatcher:
    return ToolDispatcher(registry)


async def test_dispatcher_validates_and_executes(dispatcher: ToolDispatcher) -> None:
    result = await dispatcher.dispatch(
        ToolCall(name="test.echo", arguments={"text": "hello"}), session_id="test"
    )
    assert result.success is True
    assert result.data == "hello"


async def test_dispatcher_returns_operational_failure(dispatcher: ToolDispatcher) -> None:
    registry = ToolRegistry()
    registry.register(FailingTool())
    d = ToolDispatcher(registry)
    result = await d.dispatch(ToolCall(name="test.fail"), session_id="test")
    assert result.success is False
    assert result.error is not None
    assert "intentional failure" in result.error


async def test_dispatcher_enforces_tool_timeout() -> None:
    registry = ToolRegistry()
    registry.register(SlowTool())
    d = ToolDispatcher(registry)
    result = await d.dispatch(ToolCall(name="test.slow"), session_id="test")
    assert result.success is False
    assert "timed out" in result.error.lower()


def test_registry_rejects_duplicates_and_missing_tools() -> None:
    registry = ToolRegistry()
    registry.register(EchoTool())
    with pytest.raises(ValueError, match="already registered"):
        registry.register(EchoTool())
    with pytest.raises(ToolNotFoundError):
        registry.get("missing")


async def test_dispatcher_handles_invalid_arguments() -> None:
    registry = ToolRegistry()
    registry.register(EchoTool())
    d = ToolDispatcher(registry)
    result = await d.dispatch(ToolCall(name="test.echo", arguments={"wrong": "arg"}), session_id="test")
    assert result.success is False
    assert result.error is not None


def test_registry_definitions_format() -> None:
    registry = ToolRegistry()
    registry.register(EchoTool())
    defs = registry.definitions()
    assert len(defs) == 1
    d = defs[0]
    assert d["name"] == "test.echo"
    assert "description" in d
    assert "input_schema" in d
    assert d["input_schema"]["type"] == "object"
    assert "text" in d["input_schema"]["properties"]