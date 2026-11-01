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

        log.info("Alterra initialized. Model: %s", self._settings.model)

    async def run(self) -> None:
        """Run the CLI."""
        if not self._application:
            raise RuntimeError("Application not initialized")
        await run_cli(self._application, self._settings.model)

    async def shutdown(self) -> None:
        """Clean up resources."""
        log.info("Shutting down Alterra...")
        if self._model:
            await self._model.close()
        log.info("Alterra stopped.")


async def main() -> None:
    """Entry point."""
    settings = Settings()
    app = Application(settings)
    try:
        await app.initialize()
        await app.run()
    finally:
        await app.shutdown()


if __name__ == "__main__":
    asyncio.run(main())