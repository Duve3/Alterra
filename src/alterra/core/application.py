"""Top-level interaction orchestration. It does not implement reasoning or tools."""

from __future__ import annotations

from ..agent.runtime import AgentRuntime
from ..tools.dispatcher import ToolDispatcher
from .errors import AgentError
from .messages import AssistantMessage, ToolResult, UserMessage
from .session import Session


class AlterraApplication:
    def __init__(self, agent: AgentRuntime, dispatcher: ToolDispatcher, *, max_tool_rounds: int = 8):
        self._agent = agent
        self._dispatcher = dispatcher
        self._max_tool_rounds = max_tool_rounds
        self._sessions: dict[str, Session] = {}

    def session(self, session_id: str) -> Session:
        return self._sessions.setdefault(session_id, Session(id=session_id))

    async def handle_message(self, message: UserMessage) -> AssistantMessage:
        session = self.session(message.session_id)
        session.append(message)
        for _ in range(self._max_tool_rounds):
            response = await self._agent.generate(session.messages)
            if response.message is not None:
                session.append(response.message)
                return response.message
            if not response.tool_calls:
                raise AgentError("Model returned neither an assistant message nor tool calls")
            for call in response.tool_calls:
                result: ToolResult = await self._dispatcher.dispatch(call, session_id=session.id)
                session.append(result)
        raise AgentError(f"Tool round limit ({self._max_tool_rounds}) exceeded")
