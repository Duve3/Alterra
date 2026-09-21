"""Voice backends package."""

from .mock import (
    MockAudioBackend,
    MockAudioPlayer,
    MockSTTBackend,
    MockTTSBackend,
    MockVADBackend,
    MockWakeWordBackend,
)

# Real backends are imported lazily to avoid hard dependencies
# from .real import FasterWhisperSTT, PiperTTS, SileroVAD, OpenWakeWord, PyAudioBackend

__all__ = [
    "MockWakeWordBackend",
    "MockVADBackend",
    "MockSTTBackend",
    "MockTTSBackend",
    "MockAudioBackend",
    "MockAudioPlayer",
]
