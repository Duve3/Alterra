"""Voice backends - mock and real implementations."""

from .mock import (
    MockAudioBackend,
    MockAudioPlayer,
    MockSTTBackend,
    MockTTSBackend,
    MockVADBackend,
    MockWakeWordBackend,
)
from .real import (
    FasterWhisperSTT,
    OpenWakeWord,
    PiperTTS,
    SileroVAD,
    SoundDeviceBackend,
    SoundDevicePlayer,
)

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
    "SoundDevicePlayer",
]