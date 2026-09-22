#!/usr/bin/env python
"""Example: Voice pipeline demo using mock backends.

This demonstrates the Alterra voice subsystem with a complete
wake word → VAD → STT → TTS pipeline using mock backends.
"""

from __future__ import annotations

import asyncio

from alterra.core.config import Settings
from alterra.core.messages import UserMessage
from alterra.main import build_application


async def demo_voice_pipeline() -> None:
    """Run a voice pipeline demo."""
    print("=== Voice Pipeline Demo ===\n")

    app = build_application(Settings(model_provider="local"))

    # Test voice tools using natural language
    print("\n--- Voice Tools ---")

    # Voice status
    reply = await app.handle_message(UserMessage(content="voice status", session_id="voice-demo"))
    print(f"Status: {reply.content}")

    # Voice speak
    reply = await app.handle_message(
        UserMessage(content="voice speak Hello from Alterra!", session_id="voice-demo")
    )
    print(f"Speak: {reply.content}")

    # Voice listen
    reply = await app.handle_message(UserMessage(content="voice listen 5", session_id="voice-demo"))
    print(f"Listen: {reply.content}")

    # Voice stop
    reply = await app.handle_message(UserMessage(content="voice stop", session_id="voice-demo"))
    print(f"Stop: {reply.content}")

    print("\n=== Demo complete ===")


if __name__ == "__main__":
    asyncio.run(demo_voice_pipeline())
