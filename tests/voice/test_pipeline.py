"""Tests for voice pipeline."""

import asyncio

import pytest

from alterra.voice.backends.mock import (
    MockAudioBackend,
    MockSTTBackend,
    MockTTSBackend,
    MockVADBackend,
    MockWakeWordBackend,
)
from alterra.voice.core import AudioChunk
from alterra.voice.pipeline import VoiceConfig, VoicePipeline, VoiceState


@pytest.fixture
def pipeline() -> VoicePipeline:
    audio = MockAudioBackend()
    wake_word = MockWakeWordBackend()
    vad = MockVADBackend()
    stt = MockSTTBackend()
    tts = MockTTSBackend()

    return VoicePipeline(
        audio_backend=audio,
        wake_word=wake_word,
        vad=vad,
        stt=stt,
        tts=tts,
    )


async def test_pipeline_start_stop(pipeline: VoicePipeline) -> None:
    assert not pipeline.is_running
    await pipeline.start()
    assert pipeline.is_running
    assert pipeline.state == VoiceState.LISTENING_WAKE

    # Start again (idempotent)
    await pipeline.start()
    assert pipeline.is_running

    await pipeline.stop()
    assert not pipeline.is_running
    assert pipeline.state == VoiceState.STOPPED

    # Stop again (idempotent)
    await pipeline.stop()
    assert not pipeline.is_running


async def test_pipeline_start_without_wake_word() -> None:
    """Pipeline without wake word goes directly to LISTENING_SPEECH."""
    audio = MockAudioBackend()
    vad = MockVADBackend()
    stt = MockSTTBackend()
    tts = MockTTSBackend()

    pipeline = VoicePipeline(
        audio_backend=audio,
        wake_word=None,
        vad=vad,
        stt=stt,
        tts=tts,
    )
    await pipeline.start()
    assert pipeline.state == VoiceState.LISTENING_SPEECH
    await pipeline.stop()


async def test_pipeline_wake_word_detection(pipeline: VoicePipeline) -> None:
    await pipeline.start()

    # Mock a wake word detection by patching the wake word backend
    from alterra.voice.core import WakeWordResult

    wake_detected = False

    async def mock_process(chunk):
        nonlocal wake_detected
        if not wake_detected:
            wake_detected = True
            return WakeWordResult(detected=True, confidence=0.9, model_name="mock")
        return WakeWordResult(detected=False, confidence=0.0, model_name="mock")

    pipeline._wake_word.process = mock_process  # type: ignore[union-attr]

    # Send a chunk to trigger wake word
    chunk = AudioChunk(data=b"test", sample_rate=16000, channels=1)
    await pipeline._process_chunk(chunk)

    # Should transition to listening speech
    assert pipeline.state == VoiceState.LISTENING_SPEECH


async def test_pipeline_speech_detection(pipeline: VoicePipeline) -> None:
    await pipeline.start()

    # Override config for faster test
    pipeline._config.vad_silence_timeout = 0.01

    # Force wake word state to listening speech by triggering wake word
    from alterra.voice.core import WakeWordResult

    wake_detected = False

    async def mock_process(chunk):
        nonlocal wake_detected
        if not wake_detected:
            wake_detected = True
            return WakeWordResult(detected=True, confidence=0.9, model_name="mock")
        return WakeWordResult(detected=False, confidence=0.0, model_name="mock")

    pipeline._wake_word.process = mock_process  # type: ignore[union-attr]

    # Send a chunk to trigger wake word
    chunk = AudioChunk(data=b"test", sample_rate=16000, channels=1)
    await pipeline._process_chunk(chunk)

    # Now state should be LISTENING_SPEECH
    assert pipeline.state == VoiceState.LISTENING_SPEECH

    # Send speech chunks
    import struct

    loud_data = struct.pack("<" + "h" * 100, *[10000] * 100)
    speech_chunk = AudioChunk(data=loud_data, sample_rate=16000, channels=1)

    await pipeline._process_chunk(speech_chunk)
    assert len(pipeline._speech_buffer) == 1

    # Send silence chunks to trigger end of speech
    silent_chunk = AudioChunk(data=b"\x00\x00" * 100, sample_rate=16000, channels=1)
    for _ in range(5):  # Need a few chunks to trigger silence detection
        await pipeline._process_chunk(silent_chunk)
        await asyncio.sleep(0.01)  # Let event loop time advance

    # Should have processed speech
    # State should be back to listening wake
    assert pipeline.state == VoiceState.LISTENING_WAKE


async def test_pipeline_max_speech_duration(pipeline: VoicePipeline) -> None:
    """Test that max speech duration triggers finalization."""
    pipeline._config.max_speech_duration = 0.01
    pipeline._config.vad_silence_timeout = 10.0  # Disable silence timeout
    await pipeline.start()

    # Trigger wake word using real wake word backend
    chunk = AudioChunk(data=b"test", sample_rate=16000, channels=1)
    await pipeline._process_chunk(chunk)

    # Wait for max duration to trigger, then send another chunk with audio data
    await asyncio.sleep(0.05)

    # Send another chunk with some audio data to trigger the max duration check
    import struct

    speech_data = struct.pack("<" + "h" * 100, *[100] * 100)
    await pipeline._process_chunk(AudioChunk(data=speech_data, sample_rate=16000, channels=1))

    # Should have finalized and returned to listening
    assert pipeline.state == VoiceState.LISTENING_WAKE


async def test_pipeline_stt_exception_handling(pipeline: VoicePipeline) -> None:
    """Test STT exception is handled via on_error callback."""
    errors = []

    pipeline._on_error = lambda e: errors.append(e)

    # Make STT raise an exception
    async def failing_transcribe(audio_data, sample_rate, channels):
        raise RuntimeError("STT failed")

    pipeline._stt.transcribe = failing_transcribe  # type: ignore[union-attr]

    # Override config for faster test
    pipeline._config.vad_silence_timeout = 0.01

    await pipeline.start()

    # Mock wake word to detect immediately
    from alterra.voice.core import WakeWordResult

    async def mock_wake_process(chunk):
        return WakeWordResult(detected=True, confidence=0.9, model_name="mock")

    pipeline._wake_word.process = mock_wake_process  # type: ignore[union-attr]

    # Trigger wake word
    chunk = AudioChunk(data=b"test", sample_rate=16000, channels=1)
    await pipeline._process_chunk(chunk)

    # Send speech chunks
    import struct

    loud_data = struct.pack("<" + "h" * 100, *[10000] * 100)
    speech_chunk = AudioChunk(data=loud_data, sample_rate=16000, channels=1)
    await pipeline._process_chunk(speech_chunk)
    await pipeline._process_chunk(speech_chunk)

    # Send silence chunks to trigger end of speech
    silent_chunk = AudioChunk(data=b"\x00\x00" * 100, sample_rate=16000, channels=1)
    for _ in range(5):  # Need a few chunks to trigger silence detection
        await pipeline._process_chunk(silent_chunk)
        await asyncio.sleep(0.01)

    # Should have captured the error
    assert len(errors) == 1
    assert "STT failed" in str(errors[0])


async def test_pipeline_on_speech_end_callback(pipeline: VoicePipeline) -> None:
    """Test on_speech_end callback is called."""
    speech_ended = False

    def on_speech_end():
        nonlocal speech_ended
        speech_ended = True

    pipeline._on_speech_end = on_speech_end
    pipeline._config.vad_silence_timeout = 0.01

    from alterra.voice.core import WakeWordResult

    async def mock_process(chunk):
        return WakeWordResult(detected=True, confidence=0.9, model_name="mock")

    pipeline._wake_word.process = mock_process  # type: ignore[union-attr]

    await pipeline.start()

    chunk = AudioChunk(data=b"test", sample_rate=16000, channels=1)
    await pipeline._process_chunk(chunk)

    import struct

    loud_data = struct.pack("<" + "h" * 100, *[10000] * 100)
    speech_chunk = AudioChunk(data=loud_data, sample_rate=16000, channels=1)
    await pipeline._process_chunk(speech_chunk)

    silent_chunk = AudioChunk(data=b"\x00\x00" * 100, sample_rate=16000, channels=1)
    for _ in range(5):
        await pipeline._process_chunk(silent_chunk)
        await asyncio.sleep(0.01)

    assert speech_ended


async def test_pipeline_speak(pipeline: VoicePipeline) -> None:
    await pipeline.start()
    await pipeline.speak("Hello world")
    # Should complete without error


async def test_pipeline_interrupt(pipeline: VoicePipeline) -> None:
    await pipeline.start()
    # Force to speaking state by calling speak
    await pipeline.speak("Hello")
    # Now interrupt
    await pipeline.interrupt()
    assert pipeline.state == VoiceState.LISTENING_WAKE


async def test_pipeline_speak_not_running() -> None:
    """Speak should raise error when pipeline not running."""
    audio = MockAudioBackend()
    tts = MockTTSBackend()
    pipeline = VoicePipeline(audio_backend=audio, tts=tts)
    with pytest.raises(RuntimeError, match="Pipeline not running"):
        await pipeline.speak("Hello")


async def test_pipeline_speak_no_tts() -> None:
    """Speak should raise error when TTS not configured."""
    audio = MockAudioBackend()
    pipeline = VoicePipeline(audio_backend=audio)
    await pipeline.start()
    with pytest.raises(RuntimeError, match="TTS backend not configured"):
        await pipeline.speak("Hello")
    await pipeline.stop()


async def test_voice_config_defaults() -> None:
    config = VoiceConfig()
    assert config.sample_rate == 16000
    assert config.channels == 1
    assert config.wake_word_enabled is True
    assert config.vad_silence_timeout == 1.0
    assert config.max_speech_duration == 30.0


async def test_create_default_pipeline() -> None:
    from alterra.voice.pipeline import create_default_pipeline

    pipeline = await create_default_pipeline(use_mock=True)
    assert pipeline.is_running is False
    await pipeline.stop()
