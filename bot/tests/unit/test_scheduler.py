from datetime import timedelta

from apscheduler.triggers.interval import IntervalTrigger

from gastos.jobs.scheduler import build_scheduler
from gastos.services.rates import RateService
from tests.fakes import FakeRateStore
from tests.unit.test_rate_service import sources


def test_refresca_las_tasas_cada_intervalo_y_al_arrancar() -> None:
    rates = RateService(FakeRateStore(), sources(), timedelta(hours=6))
    scheduler = build_scheduler(rates, refresh_minutes=60)
    job = scheduler.get_job("refresh_rates")
    assert job is not None
    assert job.func == rates.refresh
    assert isinstance(job.trigger, IntervalTrigger)
    assert job.trigger.interval == timedelta(minutes=60)
    assert job.next_run_time is not None  # corre en cuanto arranca el bot
