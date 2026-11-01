"""Validated capability execution boundary."""

import asyncio

from pydantic import ValidationError

from ..core.errors import ToolError, ToolNotFoundError
from ..core.messages import ToolCall, ToolResult
from .base import ToolContext
from .registry import ToolRegistry


class ToolDispatcher:
    def __init__(self, registry: ToolRegistry):
        self._registry = registry

    async def dispatch(self, call: ToolCall, *, session_id: str) -> ToolResult:
        try:
            tool = self._registry.get(call.name)
        except ToolNotFoundError as error:
            return ToolResult(tool_call_id=call.id, name=call.name, success=False, error=str(error))

        try:
            arguments = tool.arguments_model.model_validate(call.arguments)
            async with asyncio.timeout(tool.timeout_seconds):
                data = await tool.execute(arguments, ToolContext(session_id=session_id))
            return ToolResult(tool_call_id=call.id, name=call.name, success=True, data=data)
        except TimeoutError:
            return ToolResult(
                tool_call_id=call.id,
                name=call.name,
                success=False,
                error=f"Tool timed out after {tool.timeout_seconds} seconds",
            )
        except (ToolError, ValidationError, ValueError) as error:
            return ToolResult(tool_call_id=call.id, name=call.name, success=False, error=str(error))