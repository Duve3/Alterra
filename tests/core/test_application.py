import pytest

from alterra.core.config import Settings
from alterra.core.errors import ConfigurationError
from alterra.core.messages import UserMessage
from alterra.core.policy import RiskLevel, ToolPolicyMetadata
from alterra.main import ConsoleConfirmationHandler, build_application
from alterra.memory import SQLiteMemoryStore


@pytest.mark.parametrize(
    ("prompt", "expected"), [("What is 15 * 4?", "60"), ('Echo "hello Alterra"', "hello Alterra")]
)
async def test_end_to_end_local_tool_loop(prompt: str, expected: str) -> None:
    application = build_application(Settings(model_provider="local"))
    reply = await application.handle_message(UserMessage(content=prompt, session_id="test"))
    assert reply.content == expected


async def test_session_retains_interaction_history() -> None:
    application = build_application(Settings(model_provider="local"))
    await application.handle_message(UserMessage(content="Echo hello", session_id="same"))
    assert len(application.session("same").messages) == 3


def test_openrouter_profile_requires_a_key() -> None:
    with pytest.raises(ConfigurationError, match="ALTERRA_OPENROUTER_API_KEY"):
        build_application(Settings(model_provider="openrouter", openrouter_api_key=None))


def test_openrouter_profile_builds_without_touching_core_contracts() -> None:
    application = build_application(
        Settings(
            model_provider="openrouter",
            openrouter_api_key="test-key",
            openrouter_model="openai/gpt-5",
        )
    )
    assert application is not None


def test_openai_profile_requires_a_key_and_builds_when_configured() -> None:
    with pytest.raises(ConfigurationError, match="ALTERRA_OPENAI_API_KEY"):
        build_application(Settings(model_provider="openai", openai_api_key=None))
    assert (
        build_application(Settings(model_provider="openai", openai_api_key="test-key")) is not None
    )


async def test_console_confirmation_accepts_only_explicit_yes() -> None:
    from alterra.core.policy import PolicyRequest

    request = PolicyRequest(
        tool_name="test.tool",
        metadata=ToolPolicyMetadata(risk_level=RiskLevel.HIGH),
        arguments={},
        session_id="test",
    )
    assert await ConsoleConfirmationHandler(lambda _: "yes").confirm(request) is True
    assert await ConsoleConfirmationHandler(lambda _: "").confirm(request) is False


def test_application_composes_explicit_memory_service(tmp_path) -> None:
    application = build_application(
        Settings(model_provider="local", database_path=tmp_path / "memory.db")
    )
    assert isinstance(application.memory, SQLiteMemoryStore)


async def test_cli_processes_messages_and_stops(monkeypatch, capsys) -> None:
    inputs = iter(["Echo hello", "exit"])
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))
    from alterra.main import run_cli

    await run_cli(build_application(Settings(model_provider="local")))
    assert "Alterra: hello" in capsys.readouterr().out


def test_main_composes_cli(monkeypatch) -> None:
    import alterra.main as main_module

    captured = {}
    monkeypatch.setattr(main_module, "Settings", lambda: Settings(model_provider="local"))
    monkeypatch.setattr(
        main_module.asyncio,
        "run",
        lambda coroutine: (coroutine.close(), captured.setdefault("run", True)),
    )
    main_module.main()
    assert captured["run"] is True
