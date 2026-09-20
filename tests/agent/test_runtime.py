from alterra.agent.model import AgentResponse
from alterra.core.messages import AssistantMessage, ToolCall


def test_agent_response_requires_exactly_one_output_kind() -> None:
    assert AgentResponse(message=AssistantMessage(content="ok")).message is not None
    assert AgentResponse(tool_calls=[ToolCall(name="echo.repeat")]).tool_calls
