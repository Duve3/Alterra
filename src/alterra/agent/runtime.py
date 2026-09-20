"""Reasoning adapter: it offers model context and interprets no external capabilities."""

from ..core.session import ConversationMessage
from ..tools.registry import ToolRegistry
from .model import AgentResponse, Model


class AgentRuntime:
    def __init__(self, model: Model, tools: ToolRegistry):
        self._model = model
        self._tools = tools

    async def generate(self, messages: list[ConversationMessage]) -> AgentResponse:
        return await self._model.generate(messages, self._tools.definitions())
