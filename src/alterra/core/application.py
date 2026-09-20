"""Top-level interaction orchestration. It does not implement reasoning or tools."""

from __future__ import annotations

from ..agent.runtime import AgentRuntime
from ..tools.dispatcher import ToolDispatcher
from ..tools.registry import ToolRegistry
from .errors import AgentError, ToolNotFoundError
from .messages import AssistantMessage, ToolResult, UserMessage
from .policy import ConfirmationHandler, Policy, PolicyRequest, RejectingConfirmationHandler
from .session import Session


class AlterraApplication:
    def __init__(
        self,
        agent: AgentRuntime,
        registry: ToolRegistry,
        dispatcher: ToolDispatcher,
        policy: Policy,
        confirmation_handler: ConfirmationHandler | None = None,
        *,
        max_tool_rounds: int = 8,
    ):
        self._agent = agent
        self._registry = registry
        self._dispatcher = dispatcher
        self._policy = policy
        self._confirmation_handler = confirmation_handler or RejectingConfirmationHandler()
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
                result = await self._execute_call(call=call, session_id=session.id)
                session.append(result)
        raise AgentError(f"Tool round limit ({self._max_tool_rounds}) exceeded")

    async def _execute_call(self, *, call, session_id: str) -> ToolResult:
        try:
            tool = self._registry.get(call.name)
        except ToolNotFoundError as error:
            return ToolResult(tool_call_id=call.id, name=call.name, success=False, error=str(error))
        request = PolicyRequest(
            tool_name=call.name,
            arguments=call.arguments,
            metadata=tool.metadata,
            session_id=session_id,
        )
        decision = self._policy.evaluate(request)
        if not decision.allowed:
            return ToolResult(tool_call_id=call.id, name=call.name, success=False, error=decision.reason)
        if decision.requires_confirmation and not await self._confirmation_handler.confirm(request):
            return ToolResult(tool_call_id=call.id, name=call.name, success=False, error="User declined confirmation")
        return await self._dispatcher.dispatch(call, session_id=session_id)
