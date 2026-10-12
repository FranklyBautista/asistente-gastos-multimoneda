"""Configuración del bot, validada al arrancar con pydantic-settings."""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: Literal["dev", "prod"] = "dev"
    telegram_bot_token: str
    allowed_telegram_ids: list[int]
    database_url: str
    llm_provider: Literal["gemini", "groq"] = "gemini"
    gemini_api_key: str | None = None
    groq_api_key: str | None = None
    rates_api_key: str | None = None
    webhook_url: str | None = None
    webhook_secret: str | None = None


@lru_cache
def get_settings() -> Settings:
    """Devuelve la configuración; lanza ValidationError si falta algo obligatorio."""
    return Settings()  # pyright: ignore[reportCallIssue]
