"""Configuration: TOML file + environment variables. OpenRouter only for MVP."""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="ALTERRA_",
        extra="ignore",
    )

    # LLM configuration
    model: str = "meta-llama/llama-3.1-8b-instruct:free"
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=2048, gt=0)
    allow_provider_fallbacks: bool = False

    # API keys (from env only)
    openrouter_api_key: str | None = Field(default=None, repr=False)
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    # Voice configuration
    voice_enabled: bool = False
    voice_sample_rate: int = Field(default=16000, ge=8000, le=48000)
    voice_channels: int = Field(default=1, ge=1, le=2)
    voice_input_device: int | None = None
    voice_output_device: int | None = None
    voice_wake_word: bool = True
    voice_wake_word_model: str = "hey_jarvis"
    voice_wake_word_threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    voice_vad_threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    voice_vad_silence_timeout: float = Field(default=1.0, ge=0.1, le=10.0)
    voice_max_speech_duration: float = Field(default=30.0, ge=1.0, le=300.0)
    voice_stt_model: str = "base"
    voice_stt_device: str = "auto"
    voice_stt_compute_type: str = "auto"
    voice_tts_voice: str = "en_US-lessac-medium"
    voice_tts_model_dir: str | None = None
    voice_tts_use_cuda: bool = False

    # Application
    log_level: str = "INFO"
    max_tool_rounds: int = Field(default=8, ge=1, le=32)
    database_path: Path = Path("data/alterra.db")