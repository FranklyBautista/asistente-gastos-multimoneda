"""Topes por categoría y colchón en días: reglas puras (Fase 12)."""

from datetime import date, datetime
from decimal import Decimal
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from gastos.domain.budget import (
    Budget,
    BudgetProgress,
    days_left_in_month,
    month_window,
    suggested_limit,
)
from gastos.domain.runway import Runway, RunwayUnknown, runway, window_days

CARACAS = ZoneInfo("America/Caracas")
D = Decimal


def _progress(limit: str, spent: str) -> BudgetProgress:
    return BudgetProgress(Budget(uuid4(), "comida", D(limit)), D(spent), days_left=12)


@pytest.mark.parametrize(
    ("spent", "state", "pct"),
    [
        ("0", "ok", D(0)),
        ("79.99", "ok", D(80)),
        ("80", "near", D(80)),
        ("100", "near", D(100)),
        ("112", "over", D(112)),
    ],
)
def test_estado_del_tope(spent: str, state: str, pct: Decimal) -> None:
    progress = _progress("100", spent)
    assert progress.state == state
    assert progress.used_pct == pct
    assert progress.remaining_usd == D(100) - D(spent)


def test_el_mes_del_tope_es_el_calendario_local() -> None:
    now = datetime(2026, 11, 19, 15, 0, tzinfo=CARACAS)
    start, end = month_window(now)
    assert start == datetime(2026, 11, 1, tzinfo=CARACAS)
    assert end == now
    assert days_left_in_month(now) == 12
    assert days_left_in_month(datetime(2026, 11, 30, 23, 0, tzinfo=CARACAS)) == 1
    assert days_left_in_month(datetime(2026, 12, 1, 0, 5, tzinfo=CARACAS)) == 31


@pytest.mark.parametrize(
    ("months", "expected"),
    [
        ([D("62"), D("80"), D("71")], D(75)),
        ([D("40")], D(40)),
        ([D("0.5")], D(5)),
        ([D(0), D(0)], None),
        ([], None),
    ],
)
def test_tope_sugerido(months: list[Decimal], expected: Decimal | None) -> None:
    assert suggested_limit(months) == expected


def test_ventana_del_promedio() -> None:
    today = date(2026, 11, 19)
    assert window_days(None, today) is None
    assert window_days(today, today) == 1
    assert window_days(date(2026, 11, 1), today) == 19
    assert window_days(date(2025, 1, 1), today) == 90


def test_colchon_en_dias() -> None:
    result = runway(D("300"), D("900"), 90)  # 10 USD al día
    assert result == Runway(D("300"), D("10.00"), 30, 90)
    assert isinstance(result, Runway)
    assert result.next_step == 60


def test_el_colchon_redondea_hacia_abajo_y_marca_el_siguiente_escalon() -> None:
    result = runway(D("125"), D("200"), 20)  # 10 al día → 12,5 días
    assert isinstance(result, Runway)
    assert result.days == 12
    assert result.next_step == 14
    assert runway(D("10000"), D("90"), 90) == Runway(D("10000"), D("1.00"), 10000, 90)
    assert Runway(D(1), D(1), 90, 90).next_step is None


def test_saldo_negativo_es_colchon_cero() -> None:
    result = runway(D("-40"), D("300"), 30)
    assert isinstance(result, Runway)
    assert result.days == 0


@pytest.mark.parametrize(
    ("days", "expenses", "reason"),
    [(None, "0", "no_history"), (13, "100", "short_history"), (30, "0", "no_expenses")],
)
def test_sin_datos_suficientes_no_hay_colchon(days: int | None, expenses: str, reason: str) -> None:
    result = runway(D("100"), D(expenses), days)
    assert isinstance(result, RunwayUnknown)
    assert result.reason == reason
