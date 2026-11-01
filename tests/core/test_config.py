"""Tests for configuration."""

import pytest

from alterra.core.config import Settings


def test_valid_configuration() -> None:
    settings = Settings(
        openrouter_api_key="test-key",
        model="openrouter/auto",
    )
    assert settings.openrouter_api_key == "test-key"
    assert settings.model == "openrouter/auto"
    assert settings.temperature == 0.7
    assert settings.max_tokens == 2048
    assert settings.allow_provider_fallbacks is False


def test_model_required() -> None:
    # Model has a default, so this should work
    settings = Settings(openrouter_api_key="test-key", model="openrouter/free")
    assert settings.model == "openrouter/free"


def test_invalid_temperature() -> None:
    with pytest.raises(ValueError):
        Settings(openrouter_api_key="test-key", temperature=3.0)


def test_invalid_max_tokens() -> None:
    with pytest.raises(ValueError):
        Settings(openrouter_api_key="test-key", max_tokens=0)


def test_allow_provider_fallbacks_default_false() -> None:
    settings = Settings(openrouter_api_key="test-key")
    assert settings.allow_provider_fallbacks is False


def test_allow_provider_fallbacks_can_be_true() -> None:
    settings = Settings(openrouter_api_key="test-key", allow_provider_fallbacks=True)
    assert settings.allow_provider_fallbacks is True


def test_max_tool_rounds_bounds() -> None:
    settings = Settings(openrouter_api_key="test-key", max_tool_rounds=1)
    assert settings.max_tool_rounds == 1

    settings = Settings(openrouter_api_key="test-key", max_tool_rounds=32)
    assert settings.max_tool_rounds == 32

    with pytest.raises(ValueError):
        Settings(openrouter_api_key="test-key", max_tool_rounds=0)

    with pytest.raises(ValueError):
        Settings(openrouter_api_key="test-key", max_tool_rounds=33)