"""Rangos de fechas resueltos en código, en la zona horaria del usuario."""

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from gastos.domain.periods import PERIODS, Period, resolve_range

CARACAS = ZoneInfo("America/Caracas")
# Sábado 31 de octubre de 2026, 15:30 en Caracas.
NOW = datetime(2026, 10, 31, 15, 30, tzinfo=CARACAS)


def day(year: int, month: int, d: int) -> datetime:
    return datetime(year, month, d, tzinfo=CARACAS)


@pytest.mark.parametrize(
    ("period", "start", "end"),
    [
        ("today", day(2026, 10, 31), day(2026, 11, 1)),
        ("yesterday", day(2026, 10, 30), day(2026, 10, 31)),
        ("this_week", day(2026, 10, 26), day(2026, 11, 2)),  # de lunes a lunes
        ("last_week", day(2026, 10, 19), day(2026, 10, 26)),
        ("last_7_days", day(2026, 10, 25), day(2026, 11, 1)),  # hoy incluido
        ("this_month", day(2026, 10, 1), day(2026, 11, 1)),
        ("last_month", day(2026, 9, 1), day(2026, 10, 1)),
        ("last_30_days", day(2026, 10, 2), day(2026, 11, 1)),
        ("this_year", day(2026, 1, 1), day(2027, 1, 1)),
        ("all_time", day(2000, 1, 1), day(2026, 11, 1)),
    ],
)
def test_periodos(period: Period, start: datetime, end: datetime) -> None:
    resolved = resolve_range(period, NOW)
    assert (resolved.start, resolved.end) == (start, end)
    assert resolved.period == period


@pytest.mark.parametrize(
    ("month", "year", "start"),
    [
        (10, None, day(2026, 10, 1)),  # el mes en curso
        (12, None, day(2025, 12, 1)),  # todavía no llegó: el del año pasado
        (12, 2026, day(2026, 12, 1)),  # con año explícito se respeta
    ],
)
def test_un_mes_concreto(month: int, year: int | None, start: datetime) -> None:
    resolved = resolve_range("month", NOW, month, year)
    assert resolved.start == start
    assert resolved.end.day == 1 and resolved.end > start


def test_diciembre_termina_en_enero() -> None:
    resolved = resolve_range("this_month", datetime(2026, 12, 15, tzinfo=CARACAS))
    assert resolved.end == day(2027, 1, 1)
    assert resolved.last_day.date() == day(2026, 12, 31).date()


def test_la_zona_horaria_cambia_el_dia() -> None:
    """Las 22:00 del sábado en Caracas ya son domingo en UTC: manda la hora del usuario."""
    late = datetime(2026, 10, 31, 22, tzinfo=CARACAS)
    assert resolve_range("today", late).start == day(2026, 10, 31)


def test_el_mes_exige_un_numero_valido() -> None:
    with pytest.raises(ValueError):
        resolve_range("month", NOW)
    with pytest.raises(ValueError):
        resolve_range("month", NOW, 13)


def test_exige_zona_horaria() -> None:
    with pytest.raises(ValueError):
        resolve_range("today", datetime(2026, 10, 31))


def test_todos_los_periodos_se_resuelven() -> None:
    for period in PERIODS:
        resolved = resolve_range(period, NOW, month=3)
        assert resolved.start < resolved.end
