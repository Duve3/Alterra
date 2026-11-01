"""Tests for the OpenRouter provider."""

import json
import pytest

import httpx

from alterra.agent.model import AgentResponse
from alterra.agent.providers.openrouter import OpenRouterModel
from alterra.core.errors import AgentError
from alterra.core.messages import AssistantMessage, ToolCall, ToolResult, UserMessage


class FakeResponse:
    def __init__(self, body, status_code=200):
        self._body, self.status_code = body, status_code
        self.is_error = status_code >= 400
        self.text = "failure"

    def json(self):
        return self._body


class FakeClient:
    response = FakeResponse({"choices": [{"message": {"content": "hello"}}]})
    captured = None

    def __init__(self, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, *args, **kwargs):
        type(self).captured = (args, kwargs)
        return type(self).response

    async def aclose(self):
        pass


def make_model(**kwargs) -> OpenRouterModel:
    """Create OpenRouterModel with fake client for testing."""
    return OpenRouterModel(api_key="key", model="test-model", client=FakeClient(), **kwargs)


async def test_openrouter_adapter_translates_function_calls_and_text() -> None:
    model = make_model()
    FakeClient.response = FakeResponse({
        "choices": [{
            "message": {
                "tool_calls": [{
                    "id": "c",
                    "function": {"name": "echo.repeat", "arguments": json.dumps({"text": "hi"})}
                }]
            }
        }]
    })
    call = await model.generate(
        [UserMessage(content="hi")],
        [{"name": "echo.repeat", "description": "e", "input_schema": {}}],
    )
    FakeClient.response = FakeResponse({
        "choices": [{"message": {"content": "hello"}}]
    })
    text = await model.generate([UserMessage(content="hi")], [])
    assert call.tool_calls[0].name == "echo.repeat"
    assert text.message is not None
    assert text.message.content == "hello"
    assert FakeClient.captured is not None
    # Check provider config was sent
    payload = FakeClient.captured[1]["json"]
    assert payload["provider"]["allow_fallbacks"] is False


async def test_openrouter_adapter_surfaces_errors_and_empty_messages() -> None:
    model = make_model()
    FakeClient.response = FakeResponse({"choices": [{"message": {}}]})
    result = await model.generate([UserMessage(content="hi")], [])
    assert result.message is not None
    assert result.message.content.startswith("I was unable")
    FakeClient.response = FakeResponse({}, status_code=401)
    with pytest.raises(AgentError, match="401"):
        await model.generate([UserMessage(content="hi")], [])


async def test_openrouter_adapter_serializes_tool_results() -> None:
    model = make_model()
    FakeClient.response = FakeResponse({"choices": [{"message": {"content": "ok"}}]})
    await model.generate(
        [ToolResult(tool_call_id="call", name="echo.repeat", success=True, data="hi")], []
    )
    assert FakeClient.captured is not None
    msg = FakeClient.captured[1]["json"]["messages"][0]
    assert msg["role"] == "tool"
    assert msg["tool_call_id"] == "call"


async def test_openrouter_provider_fallbacks_config() -> None:
    model = make_model(allow_provider_fallbacks=True)
    FakeClient.response = FakeResponse({"choices": [{"message": {"content": "ok"}}]})
    await model.generate([UserMessage(content="hi")], [])
    payload = FakeClient.captured[1]["json"]
    assert payload["provider"]["allow_fallbacks"] is True


def test_agent_response_rejects_invalid_output_shapes() -> None:
    with pytest.raises(ValueError):
        AgentResponse()