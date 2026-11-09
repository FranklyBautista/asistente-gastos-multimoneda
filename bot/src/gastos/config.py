"""Configuración del bot, validada al arrancar con pydantic-settings."""

import re
from functools import lru_cache
from typing import Literal, Self

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Mínimo 16 caracteres: el secreto es lo único que impide que otro envíe updates falsos.
_SECRET_PATTERN = re.compile(r"[A-Za-z0-9_-]{16,256}")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: Literal["dev", "prod"] = "dev"
    telegram_bot_token: str
    allowed_telegram_ids: list[int]
    database_url: str
    llm_provider: Literal["gemini", "groq"] = "gemini"
    gemini_api_key: str | None = None
    groq_api_key: str | None = None
    # En orden: si uno está saturado o sin cuota, se usa el siguiente (ADR 0005).
    gemini_models: list[str] = Field(
        default=["gemini-3.5-flash", "gemini-3.5-flash-lite", "gemini-3.8-flash"], min_length=1
    )
    llm_timeout_seconds: float = Field(default=20, gt=0)
    rates_api_key: str | None = None
    rates_refresh_minutes: int = Field(default=60, ge=5)
    rates_max_age_hours: int = Field(default=6, ge=1)
    # Hora local (0–23) desde la que se envía el resumen del domingo (Fase 7).
    weekly_summary_hour: int = Field(default=18, ge=0, le=23)
    # Mensajes por minuto y por persona; protege la cuota del LLM (Fase 8, ADR 0010).
    rate_limit_per_minute: int = Field(default=20, ge=1)
    # Webhook (producción): URL pública base, sin la ruta. Vacía = modo polling.
    webhook_url: str | None = None
    webhook_secret: str | None = None
    # Puerto del servidor HTTP del webhook; Railway lo inyecta como PORT.
    port: int = Field(default=8080, ge=1, le=65535)
    # URL pública de la web (Fase 9); /vincular la muestra. Vacía = solo el código.
    web_url: str | None = None
    # URL de ping de healthchecks.io (u otro igual); vacía = sin latido externo.
    healthcheck_url: str | None = None

    @field_validator("webhook_url", "webhook_secret", "web_url", "healthcheck_url", mode="before")
    @classmethod
    def _empty_is_none(cls, value: object) -> object:
        # En .env, `WEBHOOK_URL=` sin valor significa "no configurado".
        return None if isinstance(value, str) and not value.strip() else value

    @field_validator("webhook_url")
    @classmethod
    def _https_only(cls, value: str | None) -> str | None:
        if value is not None and not value.startswith("https://"):
            raise ValueError("WEBHOOK_URL debe empezar con https:// (Telegram lo exige)")
        return value.rstrip("/") if value else value

    @field_validator("web_url")
    @classmethod
    def _http_url(cls, value: str | None) -> str | None:
        # En local la web corre en http://localhost:3000; en producción, https.
        if value is not None and not value.startswith(("https://", "http://")):
            raise ValueError("WEB_URL debe empezar con https:// o http://")
        return value.rstrip("/") if value else value

    @field_validator("webhook_secret")
    @classmethod
    def _valid_secret(cls, value: str | None) -> str | None:
        # Telegram solo acepta 1–256 caracteres de A-Z, a-z, 0-9, _ y -.
        if value is not None and not _SECRET_PATTERN.fullmatch(value):
            raise ValueError("WEBHOOK_SECRET: de 16 a 256 caracteres entre A-Z, a-z, 0-9, _ y -")
        return value

    @model_validator(mode="after")
    def _webhook_needs_secret(self) -> Self:
        if self.webhook_url and not self.webhook_secret:
            raise ValueError("Con WEBHOOK_URL también hace falta WEBHOOK_SECRET")
        return self

    @property
    def use_webhook(self) -> bool:
        return self.webhook_url is not None


@lru_cache
def get_settings() -> Settings:
    """Devuelve la configuración; lanza ValidationError si falta algo obligatorio."""
    return Settings()  # pyright: ignore[reportCallIssue]
