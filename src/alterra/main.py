"""Composition root and text-only CLI for Phase 1."""

from __future__ import annotations

import asyncio
import logging

from .agent.providers import LocalModel, OpenAIResponsesModel
from .agent.runtime import AgentRuntime
from .core.application import AlterraApplication
from .core.config import Settings
from .core.errors import ConfigurationError
from .core.messages import UserMessage
from .tools.builtin import CalculatorTool, EchoTool, TimeTool
from .tools.dispatcher import ToolDispatcher
from .tools.registry import ToolRegistry


def build_application(settings: Settings | None = None) -> AlterraApplication:
    settings = settings or Settings()
    registry = ToolRegistry()
    for tool in (CalculatorTool(), TimeTool(), EchoTool()):
        registry.register(tool)
    if settings.model_provider == "openai":
        if not settings.openai_api_key:
            raise ConfigurationError("ALTERRA_OPENAI_API_KEY is required for the openai provider")
        model = OpenAIResponsesModel(api_key=settings.openai_api_key, model=settings.model_name, base_url=settings.openai_base_url)
    else:
        model = LocalModel()
    return AlterraApplication(AgentRuntime(model, registry), ToolDispatcher(registry), max_tool_rounds=settings.max_tool_rounds)


async def run_cli(application: AlterraApplication) -> None:
    print("Alterra Phase 1. Type 'exit' to quit.")
    while (text := input("> ").strip()).lower() not in {"exit", "quit"}:
        if text:
            reply = await application.handle_message(UserMessage(content=text, session_id="cli"))
            print(f"Alterra: {reply.content}")


def main() -> None:
    logging.basicConfig(level=Settings().log_level)
    asyncio.run(run_cli(build_application()))


if __name__ == "__main__":
    main()
