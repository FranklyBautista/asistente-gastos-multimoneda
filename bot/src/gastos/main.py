"""Arranque del bot: polling en local (el webhook llega con el despliegue, Fase 8)."""

import asyncio
import sys
from datetime import timedelta

import structlog
from aiogram import Bot
from aiogram.types import BotCommand

from gastos.chat.dispatcher import build_dispatcher
from gastos.config import get_settings
from gastos.db.pool import create_pool
from gastos.db.repositories.rates import RateRepository
from gastos.db.repositories.users import UserRepository
from gastos.jobs.scheduler import build_scheduler
from gastos.observability.logging import configure_logging
from gastos.rates.base import create_http_client
from gastos.rates.sources import HttpRateSources
from gastos.services.rates import RateService
from gastos.services.users import UserService

COMMANDS = [
    BotCommand(command="start", description="Configurar moneda, tasa de Bs y zona horaria"),
    BotCommand(command="perfil", description="Ver tu configuración"),
    BotCommand(command="tasas", description="Ver las tasas de cambio vigentes"),
    BotCommand(command="ayuda", description="Qué puedo hacer"),
]


async def main() -> None:
    settings = get_settings()
    configure_logging(settings.env)
    log = structlog.get_logger()

    pool = create_pool(settings.database_url)
    await pool.open(wait=True, timeout=10)
    http = create_http_client()
    bot = Bot(settings.telegram_bot_token)
    rates = RateService(
        RateRepository(pool),
        HttpRateSources(http),
        max_age=timedelta(hours=settings.rates_max_age_hours),
    )
    dp = build_dispatcher(settings.allowed_telegram_ids, UserService(UserRepository(pool)), rates)
    scheduler = build_scheduler(rates, settings.rates_refresh_minutes)
    try:
        scheduler.start()
        await bot.set_my_commands(COMMANDS)
        log.info("bot_started", env=settings.env, allowed_users=len(settings.allowed_telegram_ids))
        await dp.start_polling(bot)
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
