"""Programador de tareas dentro del proceso del bot.

Debe correr una sola instancia del bot: con dos, cada trabajo se ejecutaría dos veces (el
resumen semanal igual se envía una sola vez, porque se reserva en la BD antes de mandarlo).
"""

from datetime import UTC, datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from gastos.services.rates import RateService
from gastos.services.updates import UpdateLedger
from gastos.services.weekly_summary import Send, WeeklySummaryService

# Cada cuánto se revisa a quién le toca el resumen: cada usuario tiene su zona horaria.
SUMMARY_CHECK_MINUTES = 15


def build_scheduler(
    rates: RateService,
    refresh_minutes: int,
    summaries: WeeklySummaryService,
    send: Send,
    updates: UpdateLedger,
) -> AsyncIOScheduler:
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
    scheduler.add_job(
        summaries.send_due,
        "cron",
        minute=f"*/{SUMMARY_CHECK_MINUTES}",
        args=[send],
        id="weekly_summaries",
        coalesce=True,
        max_instances=1,  # una corrida lenta (LLM) no se solapa con la siguiente
    )
    scheduler.add_job(
        updates.purge,
        "cron",
        hour=8,  # 04:00 en Caracas: hora de poco uso
        id="purge_processed_updates",
        coalesce=True,
        max_instances=1,
    )
    return scheduler
