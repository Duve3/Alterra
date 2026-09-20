"""Tool discovery and availability state."""

from ..core.errors import ToolNotFoundError
from .base import Tool


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"Tool already registered: {tool.name}")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool:
        try:
            return self._tools[name]
        except KeyError as error:
            raise ToolNotFoundError(f"Tool is not available: {name}") from error

    def definitions(self) -> list[dict]:
        return [tool.definition() for tool in self._tools.values()]
