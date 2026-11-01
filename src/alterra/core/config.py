"""Configuration: TOML file + environment variables. OpenRouter only for MVP."""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="ALTERRA_",
        extra="ignore",
        # Support loading from TOML via nested model
    )

    # LLM configuration
    model: str = "openrouter/auto"
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=2048, gt=0)
    allow_provider_fallbacks: bool = False

    # API keys (from env only)
    openrouter_api_key: str | None = Field(default=None, repr=False)
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    # Application
    log_level: str = "INFO"
    max_tool_rounds: int = Field(default=8, ge=1, le=32)
    database_path: Path = Path("data/alterra.db")  # For future memory, not used in MVP