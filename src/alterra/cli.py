"""Command-line interface for Alterra."""

from __future__ import annotations

import logging

from .core.application import AlterraApplication
from .core.messages import UserMessage

log = logging.getLogger(__name__)


async def run_cli(application: AlterraApplication, model_name: str) -> None:
    """Run the interactive CLI loop."""
    print("Alterra")
    print("Connected to OpenRouter")
    print(f"Model: {model_name}")
    print("Type 'exit' or 'quit' to leave, 'clear' to reset conversation.")
    print()

    session_id = "cli"

    try:
        while True:
            try:
                text = input("> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break

            if not text:
                continue

            if text.lower() in {"exit", "quit"}:
                break

            if text.lower() == "clear":
                # Clear conversation history for this session
                application._sessions.pop(session_id, None)
                print("(conversation cleared)")
                continue

            log.debug("User message: %s", text[:100])
            try:
                reply = await application.handle_message(
                    UserMessage(content=text, session_id=session_id)
                )
                print(f"Alterra: {reply.content}")
            except Exception as e:
                log.exception("Error handling message")
                print(f"Error: {e}")

            print()
    except Exception:
        log.exception("CLI error")
        raise