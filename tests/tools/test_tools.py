import asyncio

import pytest
from pydantic import BaseModel

from alterra.core.messages import ToolCall
from alterra.core.policy import RiskLevel, ToolPolicyMetadata
from alterra.core.errors import ToolNotFoundError
from alterra.tools.base import Tool, ToolContext
from alterra.tools.builtin import CalculatorTool, EchoTool
from alterra.tools.dispatcher import ToolDispatcher
from alterra.tools.registry import ToolRegistry


@pytest.fixture
def dispatcher() -> ToolDispatcher:
    registry = ToolRegistry()
    registry.register(CalculatorTool())
    registry.register(EchoTool())
    return ToolDispatcher(registry)


async def test_dispatcher_validates_and_executes(dispatcher: ToolDispatcher) -> None:
    result = await dispatcher.dispatch(ToolCall(name="calculator.evaluate", arguments={"expression": "15 * 4"}), session_id="test")
    assert result.success is True
    assert result.data == 60


async def test_dispatcher_returns_operational_failure(dispatcher: ToolDispatcher) -> None:
    result = await dispatcher.dispatch(ToolCall(name="calculator.evaluate", arguments={"expression": "__import__('os')"}), session_id="test")
    assert result.success is False
    assert result.error is not None


class EmptyArguments(BaseModel):
    pass


class SlowTool(Tool):
    name = "test.slow"
    description = "Test execution timeout behavior."
    arguments_model = EmptyArguments
    metadata = ToolPolicyMetadata(risk_level=RiskLevel.LOW, timeout_seconds=0.01)

    async def execute(self, arguments: EmptyArguments, context: ToolContext) -> str:
        await asyncio.sleep(0.1)
        return "too late"


async def test_dispatcher_enforces_tool_timeout() -> None:
    registry = ToolRegistry()
    registry.register(SlowTool())
    result = await ToolDispatcher(registry).dispatch(ToolCall(name="test.slow"), session_id="test")
    assert result.success is False
    assert result.error == "Tool timed out after 0.01 seconds"


def test_registry_rejects_duplicates_and_missing_tools() -> None:
    registry = ToolRegistry()
    registry.register(EchoTool())
    with pytest.raises(ValueError, match="already registered"):
        registry.register(EchoTool())
    with pytest.raises(ToolNotFoundError):
        registry.get("missing")
