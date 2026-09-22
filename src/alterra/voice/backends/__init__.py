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
from .real import FasterWhisperSTT, OpenWakeWord, PiperTTS, SileroVAD, SoundDeviceBackend

__all__ = [
    "FasterWhisperSTT",
    "MockAudioBackend",
    "MockAudioPlayer",
    "MockSTTBackend",
    "MockTTSBackend",
    "MockVADBackend",
    "MockWakeWordBackend",
    "OpenWakeWord",
    "PiperTTS",
    "SileroVAD",
    "SoundDeviceBackend",
]