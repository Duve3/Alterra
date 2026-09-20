"""Optional OpenAI Responses API adapter, isolated from all application contracts."""

from __future__ import annotations

import json
from typing import Any

import httpx

from ...core.errors import AgentError
from ...core.messages import AssistantMessage, ToolCall, ToolResult
from ...core.session import ConversationMessage
from ..model import AgentResponse


class OpenAIResponsesModel:
    def __init__(self, *, api_key: str, model: str, base_url: str = "https://api.openai.com/v1"):
        self._api_key, self._model = api_key, model
        self._base_url = base_url.rstrip("/")

    async def generate(self, messages: list[ConversationMessage], tools: list[dict]) -> AgentResponse:
        payload = {"model": self._model, "input": [self._input_item(item) for item in messages], "tools": [self._tool(item) for item in tools], "tool_choice": "auto"}
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(f"{self._base_url}/responses", headers={"Authorization": f"Bearer {self._api_key}"}, json=payload)
        if response.is_error:
            raise AgentError(f"OpenAI Responses request failed ({response.status_code}): {response.text}")
        output = response.json().get("output", [])
        calls = [ToolCall(id=item["call_id"], name=item["name"].replace("_", ".", 1), arguments=json.loads(item["arguments"])) for item in output if item.get("type") == "function_call"]
        if calls:
            return AgentResponse(tool_calls=calls)
        text = "".join(part.get("text", "") for item in output if item.get("type") == "message" for part in item.get("content", []) if part.get("type") == "output_text")
        return AgentResponse(message=AssistantMessage(content=text or "I was unable to produce a response."))

    @staticmethod
    def _tool(tool: dict[str, Any]) -> dict[str, Any]:
        return {"type": "function", "name": tool["name"].replace(".", "_"), "description": tool["description"], "parameters": tool["input_schema"], "strict": True}

    @staticmethod
    def _input_item(message: ConversationMessage) -> dict[str, Any]:
        if isinstance(message, ToolResult):
            return {"type": "function_call_output", "call_id": message.tool_call_id, "output": json.dumps({"success": message.success, "data": message.data, "error": message.error})}
        return {"role": message.role, "content": message.content}
