import pytest

from alterra.core.messages import UserMessage
from alterra.main import build_application


@pytest.mark.parametrize(("prompt", "expected"), [("What is 15 * 4?", "60"), ("Echo \"hello Alterra\"", "hello Alterra")])
async def test_end_to_end_local_tool_loop(prompt: str, expected: str) -> None:
    application = build_application()
    reply = await application.handle_message(UserMessage(content=prompt, session_id="test"))
    assert reply.content == expected


async def test_session_retains_interaction_history() -> None:
    application = build_application()
    await application.handle_message(UserMessage(content="Echo hello", session_id="same"))
    assert len(application.session("same").messages) == 3
