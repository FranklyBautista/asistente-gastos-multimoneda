from datetime import timedelta

from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from gastos.domain.user import User
from gastos.jobs.scheduler import build_scheduler
from gastos.services.rates import RateService
from gastos.services.updates import UpdateLedger
from gastos.services.weekly_summary import WeeklySummaryService
from tests.fakes import (
    FakeLLM,
    FakeRateStore,
    FakeRecipients,
    FakeReportStore,
    FakeSentSummaries,
    FakeUpdateStore,
)
from tests.unit.test_rate_service import sources

UPDATES = UpdateLedger(FakeUpdateStore())


async def send(user: User, text: str) -> None:
    pass


def build() -> tuple[RateService, WeeklySummaryService]:
    rates = RateService(FakeRateStore(), sources(), timedelta(hours=6))
    summaries = WeeklySummaryService(
        FakeReportStore(), rates, FakeLLM(), FakeSentSummaries(), FakeRecipients()
    )
    return rates, summaries


def test_refresca_las_tasas_cada_intervalo_y_al_arrancar() -> None:
    rates, summaries = build()
    scheduler = build_scheduler(rates, 60, summaries, send, UPDATES)
    job = scheduler.get_job("refresh_rates")
    assert job is not None
    assert job.func == rates.refresh
    assert isinstance(job.trigger, IntervalTrigger)
    assert job.trigger.interval == timedelta(minutes=60)
    assert job.next_run_time is not None  # corre en cuanto arranca el bot


def test_revisa_cada_15_minutos_a_quien_le_toca_el_resumen() -> None:
    rates, summaries = build()
    scheduler = build_scheduler(rates, 60, summaries, send, UPDATES)
    job = scheduler.get_job("weekly_summaries")
    assert job is not None
    assert job.func == summaries.send_due
    assert job.args == (send,)
    assert isinstance(job.trigger, CronTrigger)
    assert str(job.trigger.fields[6]) == "*/15"  # minuto


def test_purga_los_updates_viejos_una_vez_al_dia() -> None:
    rates, summaries = build()
    scheduler = build_scheduler(rates, 60, summaries, send, UPDATES)
    job = scheduler.get_job("purge_processed_updates")
    assert job is not None
    assert job.func == UPDATES.purge
    assert isinstance(job.trigger, CronTrigger)
    assert str(job.trigger.fields[5]) == "8"  # hora (UTC)
