"""Tests for voice core types."""

from alterra.voice.core import AudioChunk, TranscriptionResult, VADResult, WakeWordResult


def test_audio_chunk_creation() -> None:
    chunk = AudioChunk(data=b"test", sample_rate=16000, channels=1)
    assert chunk.data == b"test"
    assert chunk.sample_rate == 16000
    assert chunk.channels == 1
    assert chunk.timestamp is not None


def test_transcription_result_creation() -> None:
    result = TranscriptionResult(text="hello", confidence=0.95, language="en", duration_seconds=1.5)
    assert result.text == "hello"
    assert result.confidence == 0.95
    assert result.language == "en"
    assert result.duration_seconds == 1.5


def test_wake_word_result_creation() -> None:
    result = WakeWordResult(detected=True, confidence=0.98, model_name="test-model")
    assert result.detected is True
    assert result.confidence == 0.98
    assert result.model_name == "test-model"
    assert result.timestamp is not None


def test_vad_result_creation() -> None:
    result = VADResult(is_speech=True, confidence=0.9)
    assert result.is_speech is True
    assert result.confidence == 0.9
    assert result.timestamp is not None
