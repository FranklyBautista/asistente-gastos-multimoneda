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


def base_env(env: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    env.setenv("TELEGRAM_BOT_TOKEN", "token")
    env.setenv("ALLOWED_TELEGRAM_IDS", "[1]")
    env.setenv("DATABASE_URL", "postgresql://localhost/test")
    for name in ("WEBHOOK_URL", "WEBHOOK_SECRET", "PORT"):
        env.delenv(name, raising=False)
    return env


def test_sin_webhook_usa_polling(clean_env: pytest.MonkeyPatch) -> None:
    env = base_env(clean_env)
    env.setenv("WEBHOOK_URL", "")  # vacía, como en .env.example
    settings = Settings(_env_file=None)  # pyright: ignore[reportCallIssue]
    assert not settings.use_webhook
    assert settings.port == 8080
    assert settings.rate_limit_per_minute == 20


def test_webhook_con_secreto_y_puerto_de_railway(clean_env: pytest.MonkeyPatch) -> None:
    env = base_env(clean_env)
    env.setenv("WEBHOOK_URL", "https://bot.up.railway.app/")
    env.setenv("WEBHOOK_SECRET", "a" * 32)
    env.setenv("PORT", "3000")
    settings = Settings(_env_file=None)  # pyright: ignore[reportCallIssue]
    assert settings.use_webhook
    assert settings.webhook_url == "https://bot.up.railway.app"  # sin la barra final
    assert settings.port == 3000


@pytest.mark.parametrize(
    ("url", "secret"),
    [
        ("https://bot.up.railway.app", None),  # falta el secreto
        ("http://bot.up.railway.app", "a" * 32),  # Telegram exige https
        ("https://bot.up.railway.app", "corto"),  # menos de 16 caracteres
        ("https://bot.up.railway.app", "con espacios y signos!" * 2),
    ],
)
def test_webhook_mal_configurado_falla_al_arrancar(
    clean_env: pytest.MonkeyPatch, url: str, secret: str | None
) -> None:
    env = base_env(clean_env)
    env.setenv("WEBHOOK_URL", url)
    if secret is not None:
        env.setenv("WEBHOOK_SECRET", secret)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)  # pyright: ignore[reportCallIssue]
