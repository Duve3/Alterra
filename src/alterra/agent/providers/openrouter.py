"""OpenRouter adapter using the OpenAI-compatible Chat Completions API.

Uses httpx directly. The official openrouter SDK is a thin wrapper; this avoids the extra dep.
"""

from __future__ import annotations

import json
from typing import Any

import httpx

from ...core.errors import AgentError
from ...core.messages import AssistantMessage, ToolCall, ToolResult
from ...core.session import ConversationMessage
from ..model import AgentResponse


def _sanitize_tool_name(name: str) -> str:
    """Convert tool name to API-compatible format (dots → underscores)."""
    return name.replace(".", "_")


def _desanitize_tool_name(name: str) -> str:
    """Convert API tool name back to internal format (underscores → dots)."""
    # Only convert first underscore after a namespace prefix
    # e.g., "filesystem_read" -> "filesystem.read"
    parts = name.split("_", 1)
    if len(parts) == 2:
        return f"{parts[0]}.{parts[1]}"
    return name


class OpenRouterModel:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str = "https://openrouter.ai/api/v1",
        temperature: float = 0.7,
        max_tokens: int = 2048,
        allow_provider_fallbacks: bool = False,
        client: httpx.AsyncClient | None = None,
    ):
        self._api_key = api_key
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._allow_provider_fallbacks = allow_provider_fallbacks
        self._client = client or httpx.AsyncClient(timeout=60.0)
        self._owns_client = client is None

    async def generate(self, messages: list[ConversationMessage], tools: list[dict]) -> AgentResponse:
        # Sanitize tool names for API compatibility
        sanitized_tools = []
        for t in tools:
            sanitized = t.copy()
            sanitized["name"] = _sanitize_tool_name(t["name"])
            sanitized_tools.append(sanitized)

        payload = {
            "model": self._model,
            "messages": [self._to_openai_message(m) for m in messages],
            "tools": [self._to_openai_tool(t) for t in sanitized_tools] if sanitized_tools else None,
            "tool_choice": "auto" if sanitized_tools else None,
            "temperature": self._temperature,
            "max_tokens": self._max_tokens,
            "provider": {"allow_fallbacks": self._allow_provider_fallbacks},
        }
        # Remove None values
        payload = {k: v for k, v in payload.items() if v is not None}

        response = await self._client.post(
            f"{self._base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        if response.is_error:
            raise AgentError(f"OpenRouter request failed ({response.status_code}): {response.text}")

        data = response.json()
        choice = data["choices"][0]
        msg = choice["message"]

        if msg.get("tool_calls"):
            calls = [
                ToolCall(
                    id=tc["id"],
                    name=_desanitize_tool_name(tc["function"]["name"]),
                    arguments=json.loads(tc["function"]["arguments"]),
                )
                for tc in msg["tool_calls"]
            ]
            return AgentResponse(tool_calls=calls)

        content = msg.get("content", "") or "I was unable to produce a response."
        return AgentResponse(message=AssistantMessage(content=content))

    @staticmethod
    def _to_openai_tool(tool: dict[str, Any]) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": tool["input_schema"],
            },
        }

    @staticmethod
    def _to_openai_message(message: ConversationMessage) -> dict[str, Any]:
        if isinstance(message, ToolResult):
            return {
                "role": "tool",
                "tool_call_id": message.tool_call_id,
                "content": json.dumps({"success": message.success, "data": message.data, "error": message.error}),
            }
        role = message.role
        if role == "user":
            return {"role": "user", "content": message.content}
        if role == "assistant":
            return {"role": "assistant", "content": message.content}
        if role == "system":
            return {"role": "system", "content": message.content}
        raise ValueError(f"Unknown message role: {role}")

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()