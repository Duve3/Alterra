"""Application composition root. Builds and wires all components."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from .agent.providers import OpenRouterModel
from .agent.runtime import AgentRuntime
from .cli import run_cli
from .core.application import AlterraApplication
from .core.config import Settings
from .core.errors import ConfigurationError
from .integrations.filesystem import (
    ListFilesTool,
    ReadFileTool,
    SearchFilesTool,
    WriteFileTool,
)
from .logging_setup import setup_logging
from .tools.dispatcher import ToolDispatcher
from .tools.registry import ToolRegistry

log = logging.getLogger(__name__)


class Application:
    """Main application class managing lifecycle."""

    def __init__(self, settings: Settings):
        self._settings = settings
        self._application: AlterraApplication | None = None
        self._model: OpenRouterModel | None = None
        self._voice_pipeline = None
        self._voice_task: asyncio.Task | None = None

    async def initialize(self) -> None:
        """Initialize all components."""
        # Validate required configuration
        if not self._settings.openrouter_api_key:
            raise ConfigurationError("ALTERRA_OPENROUTER_API_KEY is required (set in .env)")

        # Setup logging
        log_file = Path("logs/alterra.log")
        setup_logging(self._settings.log_level, log_file)
        log.info("Starting Alterra...")

        # Create model
        self._model = OpenRouterModel(
            api_key=self._settings.openrouter_api_key,
            model=self._settings.model,
            base_url=self._settings.openrouter_base_url,
            temperature=self._settings.temperature,
            max_tokens=self._settings.max_tokens,
            allow_provider_fallbacks=self._settings.allow_provider_fallbacks,
        )

        # Create tool registry
        registry = ToolRegistry()
        # Register filesystem integration tools
        for tool in (
            ReadFileTool(),
            WriteFileTool(),
            ListFilesTool(),
            SearchFilesTool(),
        ):
            registry.register(tool)

        # Create agent and application
        agent = AgentRuntime(self._model, registry)
        dispatcher = ToolDispatcher(registry)
        self._application = AlterraApplication(
            agent=agent,
            registry=registry,
            dispatcher=dispatcher,
            max_tool_rounds=self._settings.max_tool_rounds,
        )

        # Initialize voice pipeline if enabled
        if self._settings.voice_enabled:
            await self._initialize_voice()

        log.info("Alterra initialized. Model: %s", self._settings.model)

    async def _initialize_voice(self) -> None:
        """Initialize and start voice pipeline."""
        from .core.messages import UserMessage
        from .voice import (
            FasterWhisperSTT,
            OpenWakeWord,
            PiperTTS,
            SileroVAD,
            SoundDeviceBackend,
            VoiceConfig,
            VoicePipeline,
        )

        config = VoiceConfig(
            sample_rate=self._settings.voice_sample_rate,
            channels=self._settings.voice_channels,
            wake_word_enabled=self._settings.voice_wake_word,
            vad_enabled=True,
            vad_silence_timeout=self._settings.voice_vad_silence_timeout,
            max_speech_duration=self._settings.voice_max_speech_duration,
        )

        # Create backends
        audio_backend = SoundDeviceBackend(
            input_device_index=self._settings.voice_input_device,
            output_device_index=self._settings.voice_output_device,
        )

        wake_word = None
        if self._settings.voice_wake_word:
            wake_word = OpenWakeWord(
                model_name=self._settings.voice_wake_word_model,
                threshold=self._settings.voice_wake_word_threshold,
            )

        vad = SileroVAD(threshold=self._settings.voice_vad_threshold)

        stt = FasterWhisperSTT(
            model_size=self._settings.voice_stt_model,
            device=self._settings.voice_stt_device,
            compute_type=self._settings.voice_stt_compute_type,
        )

        tts = PiperTTS(
            voice=self._settings.voice_tts_voice,
            model_dir=self._settings.voice_tts_model_dir,
            use_cuda=self._settings.voice_tts_use_cuda,
        )

        def on_transcription(result):
            log.info("Voice transcription: %s", result.text)
            if self._application:
                # Submit transcription as user message
                asyncio.create_task(
                    self._application.handle_message(
                        UserMessage(content=result.text, session_id="voice")
                    )
                )

        def on_wake_word(result):
            log.info("Wake word detected: %s (confidence: %.2f)", result.model_name, result.confidence)

        def on_error(e):
            log.error("Voice pipeline error: %s", e)

        self._voice_pipeline = VoicePipeline(
            audio_backend=audio_backend,
            wake_word=wake_word,
            vad=vad,
            stt=stt,
            tts=tts,
            config=config,
            on_transcription=on_transcription,
            on_wake_word=on_wake_word,
            on_error=on_error,
        )

        await self._voice_pipeline.start()
        log.info("Voice pipeline started")

    async def run(self) -> None:
        """Run the CLI."""
        if not self._application:
            raise RuntimeError("Application not initialized")
        await run_cli(self._application, self._settings.model)

    async def shutdown(self) -> None:
        """Clean up resources."""
        log.info("Shutting down Alterra...")
        if self._voice_pipeline:
            await self._voice_pipeline.stop()
        if self._model:
            await self._model.close()
        log.info("Alterra stopped.")


def main() -> None:
    """Entry point."""
    import asyncio

    settings = Settings()
    app = Application(settings)

    async def _run() -> None:
        try:
            await app.initialize()
            await app.run()
        finally:
            await app.shutdown()

    asyncio.run(_run())


if __name__ == "__main__":
    main()