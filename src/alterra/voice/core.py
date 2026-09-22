"""Voice subsystem core types and abstractions."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass
class AudioChunk:
    """A chunk of audio data."""

    data: bytes
    sample_rate: int
    channels: int
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class TranscriptionResult:
    """Result of speech-to-text transcription."""

    text: str
    confidence: float
    language: str | None = None
    duration_seconds: float = 0.0


@dataclass
class WakeWordResult:
    """Result of wake word detection."""

    detected: bool
    confidence: float
    model_name: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class VADResult:
    """Result of voice activity detection."""

    is_speech: bool
    confidence: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


class WakeWordBackend(ABC):
    """Abstract wake word detection backend."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Backend identifier."""

    @abstractmethod
    async def start(self) -> None:
        """Start the wake word detector."""

    @abstractmethod
    async def stop(self) -> None:
        """Stop the wake word detector."""

    @abstractmethod
    async def process(self, chunk: AudioChunk) -> WakeWordResult:
        """Process an audio chunk for wake word detection."""


class VADBackend(ABC):
    """Abstract voice activity detection backend."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Backend identifier."""

    @abstractmethod
    async def start(self) -> None:
        """Start the VAD."""

    @abstractmethod
    async def stop(self) -> None:
        """Stop the VAD."""

    @abstractmethod
    async def process(self, chunk: AudioChunk) -> VADResult:
        """Process an audio chunk for voice activity detection."""


class STTBackend(ABC):
    """Abstract speech-to-text backend."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Backend identifier."""

    @abstractmethod
    async def transcribe(
        self, audio: bytes, sample_rate: int, channels: int
    ) -> TranscriptionResult:
        """Transcribe complete audio buffer."""

    def transcribe_stream(
        self, audio_stream: AsyncIterator[AudioChunk]
    ) -> AsyncIterator[TranscriptionResult]:
        """Transcribe streaming audio (optional)."""

        # Default implementation: not implemented
        async def _empty():
            if False:
                yield

        return _empty()


class TTSBackend(ABC):
    """Abstract text-to-speech backend."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Backend identifier."""

    @abstractmethod
    async def synthesize(self, text: str, voice: str | None = None) -> bytes:
        """Synthesize text to audio bytes."""

    def synthesize_stream(self, text: str, voice: str | None = None) -> AsyncIterator[bytes]:
        """Synthesize text to streaming audio chunks (optional)."""

        # Default implementation: not implemented
        async def _empty():
            if False:
                yield

        return _empty()

    @property
    @abstractmethod
    def sample_rate(self) -> int:
        """Output sample rate."""

    @property
    @abstractmethod
    def voices(self) -> list[str]:
        """Available voices."""


class AudioBackend(ABC):
    """Abstract audio I/O backend."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Backend identifier."""

    def start_capture(self, sample_rate: int, channels: int) -> AsyncIterator[AudioChunk]:
        """Start capturing audio from microphone."""

        # Default implementation: not implemented
        async def _empty():
            if False:
                yield

        return _empty()

    @abstractmethod
    async def start_playback(self, sample_rate: int, channels: int) -> AudioPlayer:
        """Start audio playback, return a player object."""

    @abstractmethod
    async def stop(self) -> None:
        """Stop all audio I/O."""


class AudioPlayer(ABC):
    """Audio playback controller."""

    @abstractmethod
    async def write(self, chunk: AudioChunk) -> None:
        """Write audio chunk to playback buffer."""

    @abstractmethod
    async def flush(self) -> None:
        """Flush playback buffer."""

    @abstractmethod
    async def stop(self) -> None:
        """Stop playback immediately."""
