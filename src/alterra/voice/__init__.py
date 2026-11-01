"""Voice integration - wake word, VAD, STT, TTS pipeline."""

from .backends import (
    FasterWhisperSTT,
    MockAudioBackend,
    MockSTTBackend,
    MockTTSBackend,
    MockVADBackend,
    MockWakeWordBackend,
    OpenWakeWord,
    PiperTTS,
    SileroVAD,
    SoundDeviceBackend,
)
from .core import (
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
from .pipeline import VoiceConfig, VoicePipeline, VoiceState, create_default_pipeline

__all__ = [
    "AudioBackend",
    "AudioChunk",
    "AudioPlayer",
    "FasterWhisperSTT",
    "MockAudioBackend",
    "MockSTTBackend",
    "MockTTSBackend",
    "MockVADBackend",
    "MockWakeWordBackend",
    "OpenWakeWord",
    "PiperTTS",
    "STTBackend",
    "SileroVAD",
    "SoundDeviceBackend",
    "TTSBackend",
    "TranscriptionResult",
    "VADBackend",
    "VADResult",
    "VoiceConfig",
    "VoicePipeline",
    "VoiceState",
    "WakeWordBackend",
    "WakeWordResult",
    "create_default_pipeline",
]