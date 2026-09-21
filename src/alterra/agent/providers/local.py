"""Offline deterministic development provider, useful for tests and the initial CLI."""

from __future__ import annotations

import re

from ...core.messages import AssistantMessage, ToolCall, ToolResult, UserMessage
from ...core.session import ConversationMessage
from ..model import AgentResponse


class LocalModel:
    async def generate(
        self, messages: list[ConversationMessage], tools: list[dict]
    ) -> AgentResponse:
        last = messages[-1]
        if isinstance(last, ToolResult):
            if not last.success:
                return AgentResponse(
                    message=AssistantMessage(content=f"I couldn't complete that: {last.error}")
                )
            if last.name == "time.current":
                return AgentResponse(message=AssistantMessage(content=str(last.data["iso"])))
            if last.name == "memory.retrieve":
                results = last.data.get("results", [])
                if not results:
                    return AgentResponse(
                        message=AssistantMessage(content="I couldn't find any matching memories.")
                    )
                if len(results) == 1:
                    return AgentResponse(message=AssistantMessage(content=results[0]["content"]))
                lines = [f"- {r['content']}" for r in results]
                return AgentResponse(
                    message=AssistantMessage(
                        content="Here are the matching memories:\n" + "\n".join(lines)
                    )
                )
            if last.name == "memory.store":
                return AgentResponse(
                    message=AssistantMessage(content="Got it, I'll remember that.")
                )
            if last.name == "memory.delete":
                return AgentResponse(message=AssistantMessage(content="Memory deleted."))
            if last.name == "voice.status":
                data = last.data
                return AgentResponse(
                    message=AssistantMessage(
                        content=f"Voice pipeline: {'running' if data.get('running') else 'stopped'}, state: {data.get('state')}"
                    )
                )
            if last.name == "voice.speak":
                return AgentResponse(message=AssistantMessage(content="Done speaking."))
            if last.name == "voice.listen":
                return AgentResponse(message=AssistantMessage(content="Listening started."))
            if last.name == "voice.stop":
                return AgentResponse(message=AssistantMessage(content="Voice pipeline stopped."))
            return AgentResponse(message=AssistantMessage(content=str(last.data)))
        if not isinstance(last, UserMessage):
            return AgentResponse(message=AssistantMessage(content="How can I help?"))
        text = last.content.strip()
        echo = re.fullmatch(r"echo\s+[\"']?(.*?)[\"']?", text, flags=re.IGNORECASE)
        if echo:
            return AgentResponse(
                tool_calls=[ToolCall(name="echo.repeat", arguments={"text": echo.group(1)})]
            )
        if re.search(r"\b(time|clock)\b", text, flags=re.IGNORECASE):
            timezone = "UTC"
            zone = re.search(r"\b(?:in|for)\s+([A-Za-z_]+/[A-Za-z_]+)\b", text)
            if zone:
                timezone = zone.group(1)
            return AgentResponse(
                tool_calls=[ToolCall(name="time.current", arguments={"timezone": timezone})]
            )
        expression = re.search(
            r"(?:what is|calculate|compute)\s+([-+*/%().\d\s]+)\??$", text, flags=re.IGNORECASE
        )
        if expression and re.search(r"\d", expression.group(1)):
            return AgentResponse(
                tool_calls=[
                    ToolCall(
                        name="calculator.evaluate",
                        arguments={"expression": expression.group(1).strip()},
                    )
                ]
            )
        if re.search(r"\b(remember|store|save)\b.*\b(that|this)\b", text, flags=re.IGNORECASE):
            content = re.sub(
                r"\b(remember|store|save)\b\s+(that|this)\s+(is|was)?\s*",
                "",
                text,
                flags=re.IGNORECASE,
            ).strip()
            if content:
                return AgentResponse(
                    tool_calls=[
                        ToolCall(
                            name="memory.store", arguments={"content": content, "scope": "user"}
                        )
                    ]
                )
        if re.search(
            r"\b(what (do|did) (i|you)|recall|retrieve)\b.*\b(remember|know|tell me)\b",
            text,
            flags=re.IGNORECASE,
        ) or re.search(r"\bwhat (do|did) i\b", text, flags=re.IGNORECASE):
            query = re.sub(
                r"\b(what (do|did) (i|you)|recall|retrieve|remember|know|tell me)\b",
                "",
                text,
                flags=re.IGNORECASE,
            ).strip()
            # Treat generic queries as "retrieve all"
            normalized = query.lower().rstrip("?.")
            if normalized in {"", "about me", "everything", "all", "anything"}:
                query = ""
            return AgentResponse(
                tool_calls=[
                    ToolCall(name="memory.retrieve", arguments={"query": query, "scope": "user"})
                ]
            )
        if re.search(r"\b(forget|delete)\b.*\bmemory\b", text, flags=re.IGNORECASE):
            return AgentResponse(
                message=AssistantMessage(
                    content="To delete a memory, I need the memory ID. Use the memory.delete tool directly with the ID."
                )
            )
        if re.search(r"\bwhere (do|did) i\b", text, flags=re.IGNORECASE):
            query = re.sub(r"\bwhere (do|did) i\b", "", text, flags=re.IGNORECASE).strip()
            if query.lower().startswith("work"):
                query = "work"
            return AgentResponse(
                tool_calls=[
                    ToolCall(name="memory.retrieve", arguments={"query": query, "scope": "user"})
                ]
            )
        if re.search(r"\bvoice\s+(status|state)\b", text, flags=re.IGNORECASE):
            return AgentResponse(tool_calls=[ToolCall(name="voice.status", arguments={})])
        if re.search(r"\bvoice\s+speak\s+(.+)", text, flags=re.IGNORECASE):
            speak_text = re.sub(r"\bvoice\s+speak\s+", "", text, flags=re.IGNORECASE).strip()
            return AgentResponse(
                tool_calls=[ToolCall(name="voice.speak", arguments={"text": speak_text})]
            )
        if re.search(r"\bvoice\s+(listen|start)\b", text, flags=re.IGNORECASE):
            duration_match = re.search(r"(\d+(?:\.\d+)?)", text)
            duration = float(duration_match.group(1)) if duration_match else 10.0
            return AgentResponse(
                tool_calls=[ToolCall(name="voice.listen", arguments={"duration": duration})]
            )
        if re.search(r"\bvoice\s+(stop|quit)\b", text, flags=re.IGNORECASE):
            return AgentResponse(tool_calls=[ToolCall(name="voice.stop", arguments={})])
        return AgentResponse(
            message=AssistantMessage(
                content="I can calculate arithmetic, tell the time, echo text, manage memories (remember/recall), or control voice (speak/listen/status/stop)."
            )
        )
