"""Tests for voice tools."""

import pytest

from alterra.core.messages import ToolCall
from alterra.tools.builtin.voice import (
    VoiceListenTool,
    VoiceSpeakTool,
    VoiceStatusTool,
    VoiceStopTool,
)
from alterra.tools.dispatcher import ToolDispatcher
from alterra.tools.registry import ToolRegistry
from alterra.voice.backends.mock import MockAudioBackend, MockTTSBackend
from alterra.voice.pipeline import VoicePipeline


@pytest.fixture
def pipeline() -> VoicePipeline:
    audio = MockAudioBackend()
    tts = MockTTSBackend()
    return VoicePipeline(audio_backend=audio, tts=tts)


@pytest.fixture
def registry(pipeline: VoicePipeline) -> ToolRegistry:
    reg = ToolRegistry()
    reg.register(VoiceListenTool(pipeline))
    reg.register(VoiceSpeakTool(pipeline))
    reg.register(VoiceStatusTool(pipeline))
    reg.register(VoiceStopTool(pipeline))
    return reg


@pytest.fixture
def dispatcher(registry: ToolRegistry) -> ToolDispatcher:
    return ToolDispatcher(registry)


class TestVoiceListenTool:
    async def test_listen_starts_pipeline(self, dispatcher: ToolDispatcher) -> None:
        result = await dispatcher.dispatch(
            ToolCall(name="voice.listen", arguments={"duration": 5.0}), session_id="test"
        )
        assert result.success is True
        assert result.data["status"] == "listening"
        assert result.data["duration"] == 5.0

    async def test_listen_validates_duration(self, dispatcher: ToolDispatcher) -> None:
        result = await dispatcher.dispatch(
            ToolCall(name="voice.listen", arguments={"duration": -1.0}), session_id="test"
        )
        assert result.success is False
        assert result.error is not None
        assert "duration" in result.error.lower()

        result = await dispatcher.dispatch(
            ToolCall(name="voice.listen", arguments={"duration": 301.0}), session_id="test"
        )
        assert result.success is False
        assert result.error is not None
        assert "duration" in result.error.lower()


class TestVoiceStopTool:
    async def test_stop_stops_pipeline(self, dispatcher: ToolDispatcher) -> None:
        await dispatcher.dispatch(
            ToolCall(name="voice.listen", arguments={"duration": 1.0}), session_id="test"
        )
        result = await dispatcher.dispatch(ToolCall(name="voice.stop"), session_id="test")
        assert result.success is True
        assert result.data["status"] == "stopped"

    async def test_stop_idempotent(self, dispatcher: ToolDispatcher) -> None:
        result = await dispatcher.dispatch(ToolCall(name="voice.stop"), session_id="test")
        assert result.success is True
        assert result.data["status"] == "stopped"


class TestVoiceSpeakTool:
    async def test_speak_starts_pipeline_and_speaks(self, dispatcher: ToolDispatcher) -> None:
        result = await dispatcher.dispatch(
            ToolCall(name="voice.speak", arguments={"text": "Hello world"}), session_id="test"
        )
        assert result.success is True
        assert result.data["status"] == "spoken"
        assert result.data["text"] == "Hello world"

    async def test_speak_validates_text_length(self, dispatcher: ToolDispatcher) -> None:
        result = await dispatcher.dispatch(
            ToolCall(name="voice.speak", arguments={"text": ""}), session_id="test"
        )
        assert result.success is False
        assert result.error is not None
        assert "text" in result.error.lower()

        result = await dispatcher.dispatch(
            ToolCall(name="voice.speak", arguments={"text": "x" * 5001}), session_id="test"
        )
        assert result.success is False
        assert result.error is not None
        assert "text" in result.error.lower()


class TestVoiceStatusTool:
    async def test_status_returns_running_state(self, dispatcher: ToolDispatcher) -> None:
        await dispatcher.dispatch(
            ToolCall(name="voice.listen", arguments={"duration": 1.0}), session_id="test"
        )
        result = await dispatcher.dispatch(ToolCall(name="voice.status"), session_id="test")
        assert result.success is True
        assert result.data["running"] is True
        assert result.data["state"] == "listening_speech"
        assert "config" in result.data

    async def test_status_returns_stopped_state(self, dispatcher: ToolDispatcher) -> None:
        result = await dispatcher.dispatch(ToolCall(name="voice.status"), session_id="test")
        assert result.success is True
        assert result.data["running"] is False
        assert result.data["state"] == "idle"
        assert "config" in result.data
