"""Arranque del bot: polling en local y webhook en producción (si hay WEBHOOK_URL)."""

import asyncio
import sys
from collections.abc import Awaitable, Callable
from datetime import timedelta

import structlog
from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand

from gastos.chat.dispatcher import build_dispatcher
from gastos.chat.webhook import WEBHOOK_PATH, BackgroundUpdates, build_server, build_webhook_app
from gastos.config import Settings, get_settings
from gastos.db.pool import create_pool, ping
from gastos.db.repositories.corrections import CorrectionRepository
from gastos.db.repositories.exchanges import ExchangeRepository
from gastos.db.repositories.rates import RateRepository
from gastos.db.repositories.reports import ReportRepository
from gastos.db.repositories.summaries import SummaryRepository
from gastos.db.repositories.transactions import TransactionRepository
from gastos.db.repositories.updates import UpdateRepository
from gastos.db.repositories.users import UserRepository
from gastos.domain.user import User
from gastos.extraction.parser import Extractor
from gastos.jobs.scheduler import build_scheduler
from gastos.llm.gemini import GeminiClient
from gastos.observability.logging import configure_logging
from gastos.rates.base import create_http_client
from gastos.rates.sources import HttpRateSources
from gastos.services.corrections import CorrectionService
from gastos.services.exchanges import ExchangeService
from gastos.services.query_tools import QueryService
from gastos.services.rates import RateService
from gastos.services.transactions import TransactionService
from gastos.services.updates import UpdateLedger
from gastos.services.users import UserService
from gastos.services.weekly_summary import WeeklySummaryService

COMMANDS = [
    BotCommand(command="start", description="Configurar moneda, tasa de Bs y zona horaria"),
    BotCommand(command="perfil", description="Ver tu configuración"),
    BotCommand(command="tasas", description="Ver las tasas de cambio vigentes"),
    BotCommand(command="resumen", description="Cómo va tu semana"),
    BotCommand(command="corregir", description="Corregir lo último que anotaste"),
    BotCommand(command="ayuda", description="Qué puedo hacer"),
]


def build_llm(settings: Settings) -> GeminiClient:
    """Falla al arrancar, y no con el primer mensaje, si el LLM no está configurado."""
    if settings.llm_provider != "gemini":
        raise SystemExit(f"LLM_PROVIDER={settings.llm_provider} todavía no está implementado")
    if not settings.gemini_api_key:
        raise SystemExit("Falta GEMINI_API_KEY en bot/.env")
    return GeminiClient(
        settings.gemini_api_key,
        settings.gemini_models,
        timeout_seconds=settings.llm_timeout_seconds,
    )


async def poll(bot: Bot, dp: Dispatcher) -> None:
    """Modo local. Falla si el token tiene un webhook activo, en vez de quitárselo a producción."""
    info = await bot.get_webhook_info()
    if info.url:
        raise SystemExit(
            "Este bot tiene un webhook activo (está desplegado), así que no puede usar polling. "
            "Usa otro bot de @BotFather para desarrollo (ver docs/DESPLIEGUE.md)."
        )
    await dp.start_polling(bot)


async def serve_webhook(
    settings: Settings, bot: Bot, dp: Dispatcher, health: Callable[[], Awaitable[bool]]
) -> None:
    """Modo producción: registra el webhook en Telegram y sirve HTTP hasta recibir SIGTERM."""
    assert settings.webhook_url and settings.webhook_secret  # lo garantiza Settings
    updates = BackgroundUpdates(bot, dp)
    app = build_webhook_app(updates, bot, secret=settings.webhook_secret, health=health)
    # No se borra al apagar: en un redespliegue la instancia nueva ya lo usa.
    await bot.set_webhook(
        f"{settings.webhook_url}{WEBHOOK_PATH}",
        secret_token=settings.webhook_secret,
        allowed_updates=dp.resolve_used_update_types(),
    )
    await build_server(app, settings.port).serve()


async def main() -> None:
    settings = get_settings()
    configure_logging(settings.env)
    log = structlog.get_logger()
    llm = build_llm(settings)

    pool = create_pool(settings.database_url)
    await pool.open(wait=True, timeout=10)
    http = create_http_client()
    bot = Bot(settings.telegram_bot_token)
    rates = RateService(
        RateRepository(pool),
        HttpRateSources(http),
        max_age=timedelta(hours=settings.rates_max_age_hours),
    )
    transaction_repo = TransactionRepository(pool)
    exchanges = ExchangeService(ExchangeRepository(pool), transaction_repo, rates)
    report_repo = ReportRepository(pool)
    queries = QueryService(report_repo, transaction_repo, rates)
    corrections = CorrectionService(CorrectionRepository(pool), transaction_repo, rates)
    transactions = TransactionService(
        transaction_repo, Extractor(llm), rates, exchanges, queries, corrections
    )
    user_repo = UserRepository(pool)
    summaries = WeeklySummaryService(
        report_repo,
        rates,
        llm,
        SummaryRepository(pool),
        user_repo,
        send_hour=settings.weekly_summary_hour,
    )
    updates = UpdateLedger(UpdateRepository(pool))
    dp = build_dispatcher(
        settings.allowed_telegram_ids,
        UserService(user_repo),
        rates,
        transactions,
        summaries,
        updates,
        messages_per_minute=settings.rate_limit_per_minute,
    )

    async def send_summary(user: User, text: str) -> None:
        # En un chat privado, el id del chat es el id de Telegram del usuario.
        await bot.send_message(user.telegram_id, text)

    async def database_ok() -> bool:
        return await ping(pool)

    scheduler = build_scheduler(
        rates, settings.rates_refresh_minutes, summaries, send_summary, updates
    )
    try:
        scheduler.start()
        await bot.set_my_commands(COMMANDS)
        mode = "webhook" if settings.use_webhook else "polling"
        log.info(
            "bot_started",
            env=settings.env,
            mode=mode,
            allowed_users=len(settings.allowed_telegram_ids),
        )
        if settings.use_webhook:
            await serve_webhook(settings, bot, dp, database_ok)
        else:
            await poll(bot, dp)
    finally:
        if scheduler.running:
            scheduler.shutdown(wait=False)
        await bot.session.close()
        await http.aclose()
        await pool.close()


def run() -> None:
    # psycopg async no funciona con el ProactorEventLoop por defecto de Windows.
    loop_factory = asyncio.SelectorEventLoop if sys.platform == "win32" else None
    asyncio.run(main(), loop_factory=loop_factory)


if __name__ == "__main__":
    run()
