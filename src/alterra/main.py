"""Composition root and text-only CLI for Phase 2."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable

from .agent.providers import LocalModel, OpenAIResponsesModel, OpenRouterResponsesModel
from .agent.runtime import AgentRuntime
from .core.application import AlterraApplication
from .core.config import Settings
from .core.errors import ConfigurationError
from .core.messages import UserMessage
from .core.policy import ConfirmationHandler, DefaultPolicy, PolicyRequest
from .memory import SQLiteMemoryStore
from .tools.builtin import CalculatorTool, EchoTool, TimeTool
from .tools.dispatcher import ToolDispatcher
from .tools.registry import ToolRegistry


class ConsoleConfirmationHandler:
    """CLI adapter for the Core confirmation contract."""

    def __init__(self, prompt: Callable[[str], str] = input) -> None:
        self._prompt = prompt

    async def confirm(self, request: PolicyRequest) -> bool:
        answer = await asyncio.to_thread(
            self._prompt,
            f"Allow {request.tool_name} ({request.metadata.risk_level.value} risk) with {request.arguments}? [y/N] ",
        )
        return answer.strip().lower() in {"y", "yes"}


def build_application(
    settings: Settings | None = None,
    confirmation_handler: ConfirmationHandler | None = None,
) -> AlterraApplication:
    settings = settings or Settings()
    registry = ToolRegistry()
    for tool in (CalculatorTool(), TimeTool(), EchoTool()):
        registry.register(tool)
    if settings.model_provider == "openai":
        if not settings.openai_api_key:
            raise ConfigurationError("ALTERRA_OPENAI_API_KEY is required for the openai provider")
        model = OpenAIResponsesModel(api_key=settings.openai_api_key, model=settings.model_name, base_url=settings.openai_base_url)
    elif settings.model_provider == "openrouter":
        if not settings.openrouter_api_key:
            raise ConfigurationError("ALTERRA_OPENROUTER_API_KEY is required for the openrouter provider")
        model = OpenRouterResponsesModel(
            api_key=settings.openrouter_api_key,
            model=settings.openrouter_model,
            base_url=settings.openrouter_base_url,
            site_url=settings.openrouter_site_url,
            app_name=settings.openrouter_app_name,
        )
    else:
        model = LocalModel()
    policy = DefaultPolicy(
        denied_tools=settings.policy_denied_tools,
        confirmation_risks=settings.policy_confirmation_risks,
        risk_overrides=settings.policy_risk_overrides,
    )
    return AlterraApplication(
        AgentRuntime(model, registry),
        registry,
        ToolDispatcher(registry),
        policy,
        confirmation_handler,
        SQLiteMemoryStore(settings.database_path),
        max_tool_rounds=settings.max_tool_rounds,
    )


async def run_cli(application: AlterraApplication) -> None:
    print("Alterra Phase 2. Type 'exit' to quit.")
    while (text := input("> ").strip()).lower() not in {"exit", "quit"}:
        if text:
            reply = await application.handle_message(UserMessage(content=text, session_id="cli"))
            print(f"Alterra: {reply.content}")


def main() -> None:
    settings = Settings()
    logging.basicConfig(level=settings.log_level)
    asyncio.run(run_cli(build_application(settings, ConsoleConfirmationHandler())))


if __name__ == "__main__":  # pragma: no cover
    main()
