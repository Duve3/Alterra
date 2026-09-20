import pytest

from alterra.core.messages import ToolCall
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
