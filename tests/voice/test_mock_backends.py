"""Tests for voice mock backends."""

import asyncio
import pytest

from alterra.voice.backends.mock import (
    MockAudioBackend,
    MockAudioPlayer,
    MockSTTBackend,
    MockTTSBackend,
    MockVADBackend,
    MockWakeWordBackend,
)
from alterra.voice.core import AudioChunk


@pytest.fixture
def mock_wake_word() -> MockWakeWordBackend:
    return MockWakeWordBackend()


@pytest.fixture
def mock_vad() -> MockVADBackend:
    return MockVADBackend()


@pytest.fixture
def mock_stt() -> MockSTTBackend:
    return MockSTTBackend()


@pytest.fixture
def mock_tts() -> MockTTSBackend:
    return MockTTSBackend()


@pytest.fixture
def mock_audio() -> MockAudioBackend:
    return MockAudioBackend()


async def test_wake_word_backend(mock_wake_word: MockWakeWordBackend) -> None:
    await mock_wake_word.start()
    assert mock_wake_word._running is True

    chunk = AudioChunk(data=b"test", sample_rate=16000, channels=1)
    result = await mock_wake_word.process(chunk)
    assert result.detected is False
    assert result.model_name == "mock-wake-word"

    await mock_wake_word.stop()
    assert mock_wake_word._running is False


async def test_vad_backend(mock_vad: MockVADBackend) -> None:
    await mock_vad.start()
    assert mock_vad._running is True

    # Silent chunk
    silent_chunk = AudioChunk(data=b"\x00\x00" * 100, sample_rate=16000, channels=1)
    result = await mock_vad.process(silent_chunk)
    assert result.is_speech is False

    # Loud chunk
    import struct

    loud_data = struct.pack("<" + "h" * 100, *[10000] * 100)
    loud_chunk = AudioChunk(data=loud_data, sample_rate=16000, channels=1)
    result = await mock_vad.process(loud_chunk)
    assert result.is_speech is True

    await mock_vad.stop()


async def test_stt_backend(mock_stt: MockSTTBackend) -> None:
    result = await mock_stt.transcribe(b"fake audio data", 16000, 1)
    assert "Mock transcription" in result.text
    assert result.confidence == 0.95
    assert result.language == "en"

    # Test streaming
    chunks = [
        AudioChunk(data=b"chunk1", sample_rate=16000, channels=1),
        AudioChunk(data=b"chunk2", sample_rate=16000, channels=1),
    ]

    async def chunk_gen():
        for c in chunks:
            yield c

    stream_results = []
    async for r in mock_stt.transcribe_stream(chunk_gen()):
        stream_results.append(r)

    assert len(stream_results) == 2
    assert all("Mock streaming" in r.text for r in stream_results)


async def test_tts_backend(mock_tts: MockTTSBackend) -> None:
    assert mock_tts.sample_rate == 16000
    assert "default" in mock_tts.voices

    audio = await mock_tts.synthesize("Hello world")
    assert len(audio) > 0
    assert len(audio) % 2 == 0  # 16-bit samples

    # Test streaming
    chunks = []
    async for chunk in mock_tts.synthesize_stream("Hello"):
        chunks.append(chunk)
    assert len(chunks) > 0


async def test_audio_backend(mock_audio: MockAudioBackend) -> None:
    assert mock_audio.name == "mock-audio"

    # Test capture
    chunks = []
    async for chunk in mock_audio.start_capture(16000, 1):
        chunks.append(chunk)
        if len(chunks) >= 3:
            break
    await mock_audio.stop()

    assert len(chunks) == 3
    assert all(c.sample_rate == 16000 for c in chunks)

    # Test playback
    player = await mock_audio.start_playback(16000, 1)
    assert isinstance(player, MockAudioPlayer)

    await player.write(AudioChunk(data=b"test", sample_rate=16000, channels=1))
    await player.flush()
    await player.stop()


async def test_audio_player(mock_audio: MockAudioBackend) -> None:
    player = await mock_audio.start_playback(16000, 1)
    await player.write(AudioChunk(data=b"test", sample_rate=16000, channels=1))
    await player.flush()
    await player.stop()
    # Check that stop was called by verifying the player is stopped
    # (MockAudioPlayer sets _stopped = True on stop())
    assert getattr(player, "_stopped", False) is True
