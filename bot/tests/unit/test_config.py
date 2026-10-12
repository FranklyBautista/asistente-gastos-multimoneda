import pytest
from pydantic import ValidationError

from gastos.config import Settings

REQUIRED = ("TELEGRAM_BOT_TOKEN", "ALLOWED_TELEGRAM_IDS", "DATABASE_URL")


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    for name in REQUIRED:
        monkeypatch.delenv(name, raising=False)
    return monkeypatch


def test_falla_si_falta_una_variable_obligatoria(clean_env: pytest.MonkeyPatch) -> None:
    with pytest.raises(ValidationError) as exc:
        Settings(_env_file=None)  # pyright: ignore[reportCallIssue]
    missing = {err["loc"][0] for err in exc.value.errors()}
    assert missing == {"telegram_bot_token", "allowed_telegram_ids", "database_url"}


def test_carga_la_lista_blanca_en_json(clean_env: pytest.MonkeyPatch) -> None:
    clean_env.setenv("TELEGRAM_BOT_TOKEN", "token")
    clean_env.setenv("ALLOWED_TELEGRAM_IDS", "[123, 456]")
    clean_env.setenv("DATABASE_URL", "postgresql://localhost/test")
    settings = Settings(_env_file=None)  # pyright: ignore[reportCallIssue]
    assert settings.allowed_telegram_ids == [123, 456]
    assert settings.llm_provider == "gemini"
