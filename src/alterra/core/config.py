"""Configuration is centralized here; secrets are read only from the environment."""

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="ALTERRA_", extra="ignore")

    model_provider: Literal["local", "openai"] = "local"
    model_name: str = "gpt-5"
    openai_api_key: str | None = Field(default=None, repr=False)
    openai_base_url: str = "https://api.openai.com/v1"
    database_path: Path = Path("data/alterra.db")
    log_level: str = "INFO"
    max_tool_rounds: int = Field(default=8, ge=1, le=32)
