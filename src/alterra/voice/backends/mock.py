"""Mock voice backends for testing and development."""

from __future__ import annotations

import asyncio
import struct
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


class MockWakeWordBackend(WakeWordBackend):
    """Mock wake word backend that triggers on 'alterra' in transcriptions."""

    def __init__(self, trigger_phrase: str = "alterra") -> None:
        self._trigger_phrase = trigger_phrase.lower()
        self._running = False

    @property
    def name(self) -> str:
        return "mock-wake-word"

    async def start(self) -> None:
        self._running = True

    async def stop(self) -> None:
        self._running = False

    async def process(self, chunk: AudioChunk) -> WakeWordResult:
        # In a real implementation, this would run a model on the audio
        # For mock, we just return not detected
        return WakeWordResult(
            detected=False,
            confidence=0.0,
            model_name=self.name,
        )


class MockVADBackend(VADBackend):
    """Mock VAD backend that detects speech based on audio energy."""

    def __init__(self, threshold: float = 0.01) -> None:
        self._threshold = threshold
        self._running = False

    @property
    def name(self) -> str:
        return "mock-vad"

    async def start(self) -> None:
        self._running = True

    async def stop(self) -> None:
        self._running = False

    async def process(self, chunk: AudioChunk) -> VADResult:
        # Simple energy-based VAD for mock
        if not chunk.data:
            return VADResult(is_speech=False, confidence=0.0)
        # Calculate rough energy (RMS)
        samples = struct.unpack(f"<{len(chunk.data) // 2}h", chunk.data)
        energy = sum(s * s for s in samples) / len(samples) if samples else 0
        is_speech = energy > self._threshold * 32768 * 32768
        return VADResult(
            is_speech=is_speech,
            confidence=0.9 if is_speech else 0.1,
        )


class MockSTTBackend(STTBackend):
    """Mock STT backend for testing."""

    def __init__(self) -> None:
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
        # Return a dummy transcription based on audio length
        duration = len(audio) / (sample_rate * channels * 2)  # 16-bit
        return TranscriptionResult(
            text=f"[Mock transcription of {duration:.1f}s audio]",
            confidence=0.95,
            language="en",
            duration_seconds=duration,
        )

    def transcribe_stream(
        self, audio_stream: AsyncIterator[AudioChunk]
    ) -> AsyncIterator[TranscriptionResult]:
        async def _gen():
            async for chunk in audio_stream:
                yield TranscriptionResult(
                    text=f"[Mock streaming: {len(chunk.data)} bytes]",
                    confidence=0.9,
                    duration_seconds=len(chunk.data) / (chunk.sample_rate * chunk.channels * 2),
                )

        return _gen()


class MockTTSBackend(TTSBackend):
    """Mock TTS backend that generates silence."""

    def __init__(self, voice: str = "default") -> None:
        self._voice = voice
        self._running = False

    @property
    def name(self) -> str:
        return "mock-tts"

    @property
    def sample_rate(self) -> int:
        return 16000

    @property
    def voices(self) -> list[str]:
        return ["default", "male", "female"]

    async def start(self) -> None:
        self._running = True

    async def stop(self) -> None:
        self._running = False

    async def synthesize(self, text: str, voice: str | None = None) -> bytes:
        # Generate silence proportional to text length
        duration = len(text) * 0.05  # ~50ms per character
        samples = int(duration * self.sample_rate)
        return b"\x00\x00" * samples  # 16-bit silence

    def synthesize_stream(self, text: str, voice: str | None = None) -> AsyncIterator[bytes]:
        async def _gen():
            audio = await self.synthesize(text, voice)
            # Yield in chunks
            chunk_size = 3200  # ~100ms at 16kHz
            for i in range(0, len(audio), chunk_size):
                yield audio[i : i + chunk_size]
                await asyncio.sleep(0.01)

        return _gen()


class MockAudioPlayer(AudioPlayer):
    """Mock audio player that discards audio."""

    def __init__(self) -> None:
        self._stopped = False

    async def write(self, chunk: AudioChunk) -> None:
        if self._stopped:
            return
        # In real implementation, this would queue audio for playback

    async def flush(self) -> None:
        pass

    async def stop(self) -> None:
        self._stopped = True


class MockAudioBackend(AudioBackend):
    """Mock audio backend for testing."""

    def __init__(self) -> None:
        self._running = False
        self._capture_task: asyncio.Task | None = None

    @property
    def name(self) -> str:
        return "mock-audio"

    def start_capture(self, sample_rate: int, channels: int) -> AsyncIterator[AudioChunk]:
        async def _gen():
            self._running = True
            try:
                while self._running:
                    # Generate silence chunks
                    chunk_size = int(sample_rate * 0.1)  # 100ms chunks
                    silence = b"\x00\x00" * (chunk_size * channels)
                    yield AudioChunk(
                        data=silence,
                        sample_rate=sample_rate,
                        channels=channels,
                    )
                    await asyncio.sleep(0.1)
            finally:
                self._running = False

        return _gen()

    async def start_playback(self, sample_rate: int, channels: int) -> AudioPlayer:
        return MockAudioPlayer()

    async def stop(self) -> None:
        self._running = False
        if self._capture_task:
            self._capture_task.cancel()
            try:
                await self._capture_task
            except asyncio.CancelledError:
                pass
