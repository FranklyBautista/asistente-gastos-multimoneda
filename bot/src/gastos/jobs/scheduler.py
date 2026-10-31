"""Programador de tareas dentro del proceso del bot.

Debe correr una sola instancia del bot: con dos, cada trabajo se ejecutaría dos veces.
"""

from datetime import UTC, datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from gastos.services.rates import RateService


def build_scheduler(rates: RateService, refresh_minutes: int) -> AsyncIOScheduler:
    """Crea el programador sin arrancarlo; se arranca con `start()` dentro del event loop."""
    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(
        rates.refresh,
        "interval",
        minutes=refresh_minutes,
        id="refresh_rates",
        next_run_time=datetime.now(UTC),  # también al arrancar: no esperar al primer intervalo
        coalesce=True,  # si el proceso estuvo dormido, una sola corrida en vez de varias
        max_instances=1,
    )
    return scheduler
