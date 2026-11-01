"""Command-line interface for Alterra."""

from __future__ import annotations

import logging
import sys

from .core.application import AlterraApplication
from .core.messages import UserMessage

log = logging.getLogger(__name__)


def _safe_print(text: str) -> None:
    """Print text, handling Windows console encoding issues."""
    try:
        print(text)
    except UnicodeEncodeError:
        # Fallback: replace unencodable chars (e.g., emojis on cp1252)
        print(text.encode(sys.stdout.encoding or "utf-8", errors="replace").decode(sys.stdout.encoding or "utf-8"))


async def run_cli(application: AlterraApplication, model_name: str) -> None:
    """Run the interactive CLI loop."""
    _safe_print("Alterra")
    _safe_print("Connected to OpenRouter")
    _safe_print(f"Model: {model_name}")
    _safe_print("Type 'exit' or 'quit' to leave, 'clear' to reset conversation.")
    _safe_print("")

    session_id = "cli"

    try:
        while True:
            try:
                text = input("> ").strip()
            except (EOFError, KeyboardInterrupt):
                _safe_print("")
                break

            if not text:
                continue

            if text.lower() in {"exit", "quit"}:
                break

            if text.lower() == "clear":
                # Clear conversation history for this session
                application._sessions.pop(session_id, None)
                _safe_print("(conversation cleared)")
                continue

            log.debug("User message: %s", text[:100])
            try:
                reply = await application.handle_message(
                    UserMessage(content=text, session_id=session_id)
                )
                _safe_print(f"Alterra: {reply.content}")
            except Exception as e:
                log.exception("Error handling message")
                _safe_print(f"Error: {e}")

            _safe_print("")
    except Exception:
        log.exception("CLI error")
        raise