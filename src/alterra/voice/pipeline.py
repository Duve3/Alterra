"""Voice pipeline orchestrating wake word, VAD, STT, and TTS."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum

from .core import (
    AudioBackend,
    AudioChunk,
    AudioPlayer,
    STTBackend,
    TranscriptionResult,
    TTSBackend,
    VADBackend,
    WakeWordBackend,
    WakeWordResult,
)


class VoiceState(Enum):
    """Voice pipeline states."""

    IDLE = "idle"
    LISTENING_WAKE = "listening_wake"
    LISTENING_SPEECH = "listening_speech"
    TRANSCRIBING = "transcribing"
    SPEAKING = "speaking"
    STOPPED = "stopped"


@dataclass
class VoiceConfig:
    """Voice pipeline configuration."""

    sample_rate: int = 16000
    channels: int = 1
    wake_word_enabled: bool = True
    vad_enabled: bool = True
    vad_silence_timeout: float = 1.0  # seconds of silence to end speech
    max_speech_duration: float = 30.0  # max speech duration


@dataclass
class VoiceEvent:
    """Event emitted by voice pipeline."""

    type: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    data: dict = field(default_factory=dict)


class VoicePipeline:
    """Main voice pipeline coordinating all voice components."""

    def __init__(
        self,
        audio_backend: AudioBackend,
        wake_word: WakeWordBackend | None = None,
        vad: VADBackend | None = None,
        stt: STTBackend | None = None,
        tts: TTSBackend | None = None,
        config: VoiceConfig | None = None,
        on_transcription: Callable[[TranscriptionResult], None] | None = None,
        on_wake_word: Callable[[WakeWordResult], None] | None = None,
        on_speech_start: Callable[[], None] | None = None,
        on_speech_end: Callable[[], None] | None = None,
        on_error: Callable[[Exception], None] | None = None,
    ) -> None:
        self._audio = audio_backend
        self._wake_word = wake_word
        self._vad = vad
        self._stt = stt
        self._tts = tts
        self._config = config or VoiceConfig()
        self._state = VoiceState.IDLE
        self._running = False

        # Callbacks
        self._on_transcription = on_transcription
        self._on_wake_word = on_wake_word
        self._on_speech_start = on_speech_start
        self._on_speech_end = on_speech_end
        self._on_error = on_error

        # Internal state
        self._speech_buffer: list[AudioChunk] = []
        self._silence_start: float | None = None
        self._speech_start_time: float | None = None
        self._player: AudioPlayer | None = None
        self._tasks: list[asyncio.Task] = []

    @property
    def state(self) -> VoiceState:
        return self._state

    @property
    def is_running(self) -> bool:
        return self._running

    async def start(self) -> None:
        """Start the voice pipeline."""
        if self._running:
            return
        self._running = True
        self._state = VoiceState.LISTENING_WAKE if self._wake_word else VoiceState.LISTENING_SPEECH

        # Start backends
        if self._wake_word:
            await self._wake_word.start()
        if self._vad:
            await self._vad.start()
        if self._stt and hasattr(self._stt, "start"):
            await self._stt.start()
        if self._tts and hasattr(self._tts, "start"):
            await self._tts.start()

        # Start audio capture
        self._tasks.append(asyncio.create_task(self._run_capture()))

    async def stop(self) -> None:
        """Stop the voice pipeline."""
        self._running = False
        self._state = VoiceState.STOPPED

        # Cancel tasks
        for task in self._tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._tasks.clear()

        # Stop backends
        if self._wake_word:
            await self._wake_word.stop()
        if self._vad:
            await self._vad.stop()
        if self._stt and hasattr(self._stt, "stop"):
            await self._stt.stop()
        if self._tts and hasattr(self._tts, "stop"):
            await self._tts.stop()

        # Stop audio
        await self._audio.stop()
        if self._player:
            await self._player.stop()

    async def _run_capture(self) -> None:
        """Main audio capture loop."""
        try:
            async for chunk in self._audio.start_capture(
                self._config.sample_rate, self._config.channels
            ):
                if not self._running:
                    break
                await self._process_chunk(chunk)
        except asyncio.CancelledError:
            raise
        except Exception as e:  # noqa: BLE001
            if self._on_error:
                self._on_error(e)

    async def _process_chunk(self, chunk: AudioChunk) -> None:
        """Process an audio chunk through the pipeline."""
        # Wake word detection
        if self._state == VoiceState.LISTENING_WAKE and self._wake_word:
            result = await self._wake_word.process(chunk)
            if result.detected:
                self._state = VoiceState.LISTENING_SPEECH
                self._speech_start_time = asyncio.get_event_loop().time()
                if self._on_wake_word:
                    self._on_wake_word(result)
                # Reset speech buffer on wake word
                self._speech_buffer.clear()
                return

        # VAD processing
        if self._state == VoiceState.LISTENING_SPEECH and self._vad:
            result = await self._vad.process(chunk)
            if result.is_speech:
                self._speech_buffer.append(chunk)
                if self._silence_start is not None:
                    self._silence_start = None
            else:
                if self._silence_start is None:
                    self._silence_start = asyncio.get_event_loop().time()
                elif (
                    asyncio.get_event_loop().time() - self._silence_start
                    >= self._config.vad_silence_timeout
                ):
                    # End of speech detected
                    await self._finalize_speech()

        # Check max speech duration
        if self._speech_start_time is not None:
            elapsed = asyncio.get_event_loop().time() - self._speech_start_time
            if elapsed >= self._config.max_speech_duration:
                await self._finalize_speech()

    async def _finalize_speech(self) -> None:
        """Finalize captured speech and transcribe."""
        if not self._speech_buffer:
            self._state = (
                VoiceState.LISTENING_WAKE if self._wake_word else VoiceState.LISTENING_SPEECH
            )
            self._speech_start_time = None
            self._silence_start = None
            return

        self._state = VoiceState.TRANSCRIBING
        if self._on_speech_end:
            self._on_speech_end()

        # Combine audio chunks
        audio_data = b"".join(chunk.data for chunk in self._speech_buffer)
        sample_rate = self._speech_buffer[0].sample_rate
        channels = self._speech_buffer[0].channels

        # Clear buffer
        self._speech_buffer.clear()
        self._speech_start_time = None
        self._silence_start = None

        # Transcribe
        if self._stt:
            try:
                result = await self._stt.transcribe(audio_data, sample_rate, channels)
                if result.text and self._on_transcription:
                    self._on_transcription(result)
            except Exception as e:  # noqa: BLE001
                if self._on_error:
                    self._on_error(e)

        # Return to listening state
        self._state = VoiceState.LISTENING_WAKE if self._wake_word else VoiceState.LISTENING_SPEECH

    async def _ensure_tts_audio(self) -> None:
        """Ensure TTS and audio backends are started for speak-only operations."""
        if self._tts and hasattr(self._tts, "start"):
            await self._tts.start()

    async def speak(self, text: str, voice: str | None = None) -> None:
        """Synthesize and play text. Works without full pipeline running."""
        if not self._tts:
            raise RuntimeError("TTS backend not configured")

        # Ensure TTS and audio are ready
        await self._ensure_tts_audio()

        self._state = VoiceState.SPEAKING

        try:
            audio = await self._tts.synthesize(text, voice)
            if not self._player:
                self._player = await self._audio.start_playback(self._tts.sample_rate, 1)

            # Write audio in chunks
            chunk_size = 4096
            for i in range(0, len(audio), chunk_size):
                if self._player is None:
                    break
                chunk = AudioChunk(
                    data=audio[i : i + chunk_size],
                    sample_rate=self._tts.sample_rate,
                    channels=1,
                )
                await self._player.write(chunk)

            if self._player:
                await self._player.flush()
        finally:
            self._state = (
                VoiceState.LISTENING_WAKE if self._wake_word else VoiceState.LISTENING_SPEECH
            )

    async def interrupt(self) -> None:
        """Interrupt current speech or transcription."""
        if self._player:
            await self._player.stop()
        self._speech_buffer.clear()
        self._speech_start_time = None
        self._silence_start = None
        self._state = VoiceState.LISTENING_WAKE if self._wake_word else VoiceState.LISTENING_SPEECH


async def create_default_pipeline(
    use_mock: bool = True,
    **kwargs,
) -> VoicePipeline:
    """Create a voice pipeline with default backends."""
    if use_mock:
        from .backends.mock import (
            MockAudioBackend,
            MockSTTBackend,
            MockTTSBackend,
            MockVADBackend,
            MockWakeWordBackend,
        )

        audio = MockAudioBackend()
        wake_word = MockWakeWordBackend()
        vad = MockVADBackend()
        stt = MockSTTBackend()
        tts = MockTTSBackend()
    else:
        from .backends.real import (
            FasterWhisperSTT,
            OpenWakeWord,
            PiperTTS,
            SileroVAD,
            SoundDeviceBackend,
        )

        audio = SoundDeviceBackend()
        wake_word = OpenWakeWord()
        vad = SileroVAD()
        stt = FasterWhisperSTT()
        tts = PiperTTS()

    return VoicePipeline(
        audio_backend=audio,
        wake_word=wake_word,
        vad=vad,
        stt=stt,
        tts=tts,
        **kwargs,
    )