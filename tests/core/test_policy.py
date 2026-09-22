import pytest
from pydantic import BaseModel

from alterra.agent.model import AgentResponse
from alterra.agent.runtime import AgentRuntime
from alterra.core.application import AlterraApplication
from alterra.core.errors import AgentError
from alterra.core.messages import AssistantMessage, ToolCall, UserMessage
from alterra.core.policy import DefaultPolicy, RiskLevel, ToolPolicyMetadata
from alterra.tools.base import Tool, ToolContext
from alterra.tools.dispatcher import ToolDispatcher
from alterra.tools.registry import ToolRegistry


class EmptyArguments(BaseModel):
    pass


class HighRiskTool(Tool):
    name = "test.high_risk"
    description = "Test policy enforcement."
    arguments_model = EmptyArguments
    metadata = ToolPolicyMetadata(risk_level=RiskLevel.HIGH)

    async def execute(self, arguments: BaseModel, context: ToolContext) -> str:
        return "executed"


class OneCallModel:
    async def generate(self, messages, tools) -> AgentResponse:
        if len(messages) == 1:
            return AgentResponse(tool_calls=[ToolCall(name="test.high_risk")])
        result = messages[-1]
        return AgentResponse(
            message=AssistantMessage(content=str(result.data if result.success else result.error))
        )


class RecordingConfirmation:
    def __init__(self, answer: bool):
        self.answer = answer
        self.requests = []

    async def confirm(self, request) -> bool:
        self.requests.append(request)
        return self.answer


def build_policy_application(
    policy: DefaultPolicy, confirmation: RecordingConfirmation
) -> AlterraApplication:
    registry = ToolRegistry()
    registry.register(HighRiskTool())
    return AlterraApplication(
        AgentRuntime(OneCallModel(), registry),
        registry,
        ToolDispatcher(registry),
        policy,
        confirmation,
    )


async def test_policy_denial_prevents_execution() -> None:
    app = build_policy_application(
        DefaultPolicy(denied_tools={"test.high_risk"}), RecordingConfirmation(True)
    )
    reply = await app.handle_message(UserMessage(content="do it"))
    assert "Policy denies test.high_risk" in reply.content


async def test_high_risk_tool_requires_and_observes_confirmation() -> None:
    confirmation = RecordingConfirmation(False)
    app = build_policy_application(DefaultPolicy(), confirmation)
    reply = await app.handle_message(UserMessage(content="do it"))
    assert reply.content == "User declined confirmation"
    assert confirmation.requests[0].tool_name == "test.high_risk"


async def test_confirmation_can_authorize_policy_approved_tool() -> None:
    confirmation = RecordingConfirmation(True)
    app = build_policy_application(DefaultPolicy(), confirmation)
    reply = await app.handle_message(UserMessage(content="do it"))
    assert reply.content == "executed"


async def test_unknown_tool_becomes_an_operational_result() -> None:
    registry = ToolRegistry()

    class UnknownModel:
        async def generate(self, messages, tools) -> AgentResponse:
            if len(messages) == 1:
                return AgentResponse(tool_calls=[ToolCall(name="unknown.tool")])
            return AgentResponse(message=AssistantMessage(content=messages[-1].error))

    app = AlterraApplication(
        AgentRuntime(UnknownModel(), registry), registry, ToolDispatcher(registry), DefaultPolicy()
    )
    assert "not available" in (await app.handle_message(UserMessage(content="x"))).content


async def test_application_rejects_empty_agent_response_and_tool_loop_limit() -> None:
    registry = ToolRegistry()

    class EmptyModel:
        async def generate(self, messages, tools) -> AgentResponse:
            return AgentResponse.model_construct(message=None, tool_calls=[])

    class LoopModel:
        async def generate(self, messages, tools) -> AgentResponse:
            return AgentResponse(tool_calls=[ToolCall(name="unknown.tool")])

    empty = AlterraApplication(
        AgentRuntime(EmptyModel(), registry), registry, ToolDispatcher(registry), DefaultPolicy()
    )
    looping = AlterraApplication(
        AgentRuntime(LoopModel(), registry),
        registry,
        ToolDispatcher(registry),
        DefaultPolicy(),
        max_tool_rounds=1,
    )
    with pytest.raises(AgentError, match="neither"):
        await empty.handle_message(UserMessage(content="x"))
    with pytest.raises(AgentError, match="round limit"):
        await looping.handle_message(UserMessage(content="x"))


async def test_rejecting_confirmation_handler_denies() -> None:
    from alterra.core.policy import (
        PolicyRequest,
        RejectingConfirmationHandler,
        RiskLevel,
        ToolPolicyMetadata,
    )

    request = PolicyRequest(
        tool_name="test.tool",
        metadata=ToolPolicyMetadata(risk_level=RiskLevel.HIGH),
        arguments={},
        session_id="test",
    )
    assert await RejectingConfirmationHandler().confirm(request) is False


def test_policy_honors_risk_overrides_and_explicit_confirmation() -> None:
    from alterra.core.policy import PolicyRequest, RiskLevel, ToolPolicyMetadata

    request = PolicyRequest(
        tool_name="test.low",
        metadata=ToolPolicyMetadata(risk_level=RiskLevel.LOW, requires_confirmation=True),
        arguments={},
        session_id="s",
    )
    decision = DefaultPolicy(risk_overrides={"test.low": RiskLevel.HIGH}).evaluate(request)
    assert decision.allowed is True
    assert decision.requires_confirmation is True
