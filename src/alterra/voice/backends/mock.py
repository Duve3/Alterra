"""Mock voice backends for testing."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from ..core import (
    AudioBackend,
    AudioChunk,
    AudioPlayer,
    STTBackend,
    TranscriptionResult,
    TTSBackend,
    VADBackend,
    VADResult,
    WakeWordBackend,
    WakeWordResult,
)


class MockAudioBackend(AudioBackend):
    """Mock audio backend for testing."""

    def __init__(self) -> None:
        self._running = False

    @property
    def name(self) -> str:
        return "mock-audio"

    async def start_capture(self, sample_rate: int, channels: int) -> AsyncIterator[AudioChunk]:
        """Yield silent audio chunks for testing."""
        self._running = True
        chunk_size = int(sample_rate * 0.1 * channels * 2)  # 100ms of 16-bit audio
        silent_chunk = bytes(chunk_size)

        while self._running:
            await asyncio.sleep(0.1)
            yield AudioChunk(
                data=silent_chunk,
                sample_rate=sample_rate,
                channels=channels,
            )

    async def start_playback(self, sample_rate: int, channels: int) -> AudioPlayer:
        return MockAudioPlayer()

    async def stop(self) -> None:
        self._running = False


class MockAudioPlayer(AudioPlayer):
    """Mock audio player for testing."""

    async def write(self, chunk: AudioChunk) -> None:
        await asyncio.sleep(0.001)  # Simulate write time

    async def flush(self) -> None:
        pass

    async def stop(self) -> None:
        pass


class MockWakeWordBackend(WakeWordBackend):
    """Mock wake word backend that triggers on 'hello alterra' in transcriptions."""

    def __init__(self, trigger_on: str = "hello alterra") -> None:
        self._trigger_on = trigger_on.lower()
        self._running = False

    @property
    def name(self) -> str:
        return "mock-wakeword"

    async def start(self) -> None:
        self._running = True

    async def stop(self) -> None:
        self._running = False

    async def process(self, chunk: AudioChunk) -> WakeWordResult:
        # Mock: never actually detect wake word from audio
        # This would need actual audio processing in real implementation
        return WakeWordResult(
            detected=False,
            confidence=0.0,
            model_name=self.name,
        )


class MockVADBackend(VADBackend):
    """Mock VAD backend."""

    def __init__(self, always_speech: bool = False) -> None:
        self._always_speech = always_speech
        self._running = False

    @property
    def name(self) -> str:
        return "mock-vad"

    async def start(self) -> None:
        self._running = True

    async def stop(self) -> None:
        self._running = False

    async def process(self, chunk: AudioChunk) -> VADResult:
        return VADResult(
            is_speech=self._always_speech,
            confidence=1.0 if self._always_speech else 0.0,
        )


class MockSTTBackend(STTBackend):
    """Mock STT backend."""

    def __init__(self, fixed_response: str = "mock transcription") -> None:
        self._fixed_response = fixed_response
        self._running = False

    @property
    def name(self) -> str:
        return "mock-stt"

    async def start(self) -> None:
        self._running = True

    async def stop(self) -> None:
        self._running = False

    async def transcribe(
        self, audio: bytes, sample_rate: int, channels: int
    ) -> TranscriptionResult:
        return TranscriptionResult(
            text=self._fixed_response,
            confidence=0.95,
            language="en",
            duration_seconds=len(audio) / (sample_rate * channels * 2),
        )


class MockTTSBackend(TTSBackend):
    """Mock TTS backend."""

    def __init__(self) -> None:
        self._running = False

    @property
    def name(self) -> str:
        return "mock-tts"

    @property
    def sample_rate(self) -> int:
        return 22050

    @property
    def voices(self) -> list[str]:
        return ["mock-voice"]

    async def start(self) -> None:
        self._running = True

    async def stop(self) -> None:
        self._running = False

    async def synthesize(self, text: str, voice: str | None = None) -> bytes:
        # Return silence audio
        duration_samples = int(len(text) * 0.1 * self.sample_rate)
        return bytes(duration_samples * 2)  # 16-bit = 2 bytes per sample

    async def synthesize_stream(self, text: str, voice: str | None = None) -> AsyncIterator[bytes]:
        audio = await self.synthesize(text, voice)
        chunk_size = 4096
        for i in range(0, len(audio), chunk_size):
            yield audio[i : i + chunk_size]
            await asyncio.sleep(0.01)