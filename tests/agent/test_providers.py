import json

import pytest

from alterra.agent.model import AgentResponse
from alterra.agent.providers.local import LocalModel
from alterra.agent.providers.openai import OpenAIResponsesModel
from alterra.core.errors import AgentError
from alterra.core.messages import SystemMessage, ToolResult, UserMessage


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        (UserMessage(content="What time is it in America/Los_Angeles?"), "time.current"),
        (UserMessage(content="calculate -2 + 3"), "calculator.evaluate"),
        (UserMessage(content="unknown request"), None),
        (SystemMessage(content="context"), None),
    ],
)
async def test_local_model_routes_supported_and_fallback_messages(message, expected) -> None:
    response = await LocalModel().generate([message], [])
    assert (response.tool_calls[0].name if response.tool_calls else None) == expected


async def test_local_model_formats_tool_results() -> None:
    model = LocalModel()
    failed = await model.generate([ToolResult(tool_call_id="1", name="x", success=False, error="no")], [])
    timed = await model.generate(
        [ToolResult(tool_call_id="1", name="time.current", success=True, data={"iso": "now"})], []
    )
    generic = await model.generate([ToolResult(tool_call_id="1", name="x", success=True, data=3)], [])
    assert failed.message.content == "I couldn't complete that: no"
    assert timed.message.content == "now"
    assert generic.message.content == "3"


def test_agent_response_rejects_invalid_output_shapes() -> None:
    with pytest.raises(ValueError):
        AgentResponse()


class FakeResponse:
    def __init__(self, body, status_code=200):
        self._body, self.status_code = body, status_code
        self.is_error = status_code >= 400
        self.text = "failure"

    def json(self):
        return self._body


class FakeClient:
    response = FakeResponse({"output": []})
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


async def test_openai_adapter_translates_function_calls_and_text(monkeypatch) -> None:
    monkeypatch.setattr("alterra.agent.providers.openai.httpx.AsyncClient", FakeClient)
    model = OpenAIResponsesModel(api_key="key", model="model")
    FakeClient.response = FakeResponse({"output": [{"type": "function_call", "call_id": "c", "name": "echo_repeat", "arguments": json.dumps({"text": "hi"})}]})
    call = await model.generate([UserMessage(content="hi")], [{"name": "echo.repeat", "description": "e", "input_schema": {}}])
    FakeClient.response = FakeResponse({"output": [{"type": "message", "content": [{"type": "output_text", "text": "hello"}]}]})
    text = await model.generate([UserMessage(content="hi")], [])
    assert call.tool_calls[0].name == "echo.repeat"
    assert text.message.content == "hello"
    assert FakeClient.captured[1]["json"]["tools"] == []


async def test_openai_adapter_surfaces_errors_and_empty_messages(monkeypatch) -> None:
    monkeypatch.setattr("alterra.agent.providers.openai.httpx.AsyncClient", FakeClient)
    model = OpenAIResponsesModel(api_key="key", model="model")
    FakeClient.response = FakeResponse({"output": []})
    assert (await model.generate([UserMessage(content="hi")], [])).message.content.startswith("I was unable")
    FakeClient.response = FakeResponse({}, status_code=401)
    with pytest.raises(AgentError, match="401"):
        await model.generate([UserMessage(content="hi")], [])


async def test_openai_adapter_serializes_tool_results(monkeypatch) -> None:
    monkeypatch.setattr("alterra.agent.providers.openai.httpx.AsyncClient", FakeClient)
    FakeClient.response = FakeResponse({"output": []})
    await OpenAIResponsesModel(api_key="key", model="model").generate(
        [ToolResult(tool_call_id="call", name="echo.repeat", success=True, data="hi")], []
    )
    assert FakeClient.captured[1]["json"]["input"][0]["type"] == "function_call_output"
