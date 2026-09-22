"""Composition root and text-only CLI for Phase 6."""

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
from .scheduler import Scheduler, SQLiteTaskStore
from .tools.builtin import (
    CalculatorTool,
    EchoTool,
    MemoryDeleteTool,
    MemoryRetrieveTool,
    MemoryStoreTool,
    SchedulerCancelTool,
    SchedulerCreateTool,
    SchedulerListTool,
    TimeTool,
    VoiceListenTool,
    VoiceSpeakTool,
    VoiceStatusTool,
    VoiceStopTool,
)
from .tools.dispatcher import ToolDispatcher
from .tools.registry import ToolRegistry
from .voice.pipeline import VoicePipeline
from .voice.backends import SileroVAD, PiperTTS, OpenWakeWord, SoundDeviceBackend, FasterWhisperSTT


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


async def _tool_executor(tool_name: str, arguments: dict) -> None:
    """Placeholder - in real use, this would dispatch through the application."""


def build_application(
    settings: Settings | None = None,
    confirmation_handler: ConfirmationHandler | None = None,
) -> AlterraApplication:
    settings = settings or Settings()
    memory_store = SQLiteMemoryStore(settings.database_path)
    task_store = SQLiteTaskStore(settings.database_path.with_suffix(".tasks.db"))

    # Create scheduler (will be started by the CLI)
    scheduler = Scheduler(task_store, _tool_executor)

    # Create voice pipeline
    audio = SoundDeviceBackend()
    wake_word = OpenWakeWord()
    vad = SileroVAD()
    stt = FasterWhisperSTT()
    tts = PiperTTS()
    voice_pipeline = VoicePipeline(
        audio_backend=audio,
        wake_word=wake_word,
        vad=vad,
        stt=stt,
        tts=tts,
    )

    registry = ToolRegistry()
    for tool in (
        CalculatorTool(),
        TimeTool(),
        EchoTool(),
        MemoryStoreTool(memory_store),
        MemoryRetrieveTool(memory_store),
        MemoryDeleteTool(memory_store),
        SchedulerCreateTool(scheduler),
        SchedulerCancelTool(scheduler),
        SchedulerListTool(scheduler),
        VoiceListenTool(voice_pipeline),
        VoiceSpeakTool(voice_pipeline),
        VoiceStatusTool(voice_pipeline),
        VoiceStopTool(voice_pipeline),
    ):
        registry.register(tool)

    if settings.model_provider == "openai":
        if not settings.openai_api_key:
            raise ConfigurationError("ALTERRA_OPENAI_API_KEY is required for the openai provider")
        model = OpenAIResponsesModel(
            api_key=settings.openai_api_key,
            model=settings.model_name,
            base_url=settings.openai_base_url,
        )
    elif settings.model_provider == "openrouter":
        if not settings.openrouter_api_key:
            raise ConfigurationError(
                "ALTERRA_OPENROUTER_API_KEY is required for the openrouter provider"
            )
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
        memory_store,
        max_tool_rounds=settings.max_tool_rounds,
    )


async def run_cli(application: AlterraApplication) -> None:
    # Start scheduler for demo
    from .scheduler import Scheduler, SQLiteTaskStore

    task_store = SQLiteTaskStore(Settings().database_path.with_suffix(".tasks.db"))
    scheduler = Scheduler(task_store, lambda name, args: None)
    await scheduler.start()

    print("Alterra Phase 6. Type 'exit' to quit.")
    try:
        while (text := input("> ").strip()).lower() not in {"exit", "quit"}:
            if text:
                reply = await application.handle_message(
                    UserMessage(content=text, session_id="cli")
                )
                print(f"Alterra: {reply.content}")
    finally:
        await scheduler.stop()


def main() -> None:
    settings = Settings()
    logging.basicConfig(level=settings.log_level)
    asyncio.run(run_cli(build_application(settings, ConsoleConfirmationHandler())))


if __name__ == "__main__":  # pragma: no cover
    main()
