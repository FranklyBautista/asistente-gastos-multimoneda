"""Herramientas de consulta con base de datos, tasas y LLM falsos."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from gastos.domain.conversion import Rate
from gastos.domain.currency import QuotedCurrency, RateSource
from gastos.domain.reports import AccountBalance, CurrencyTotal
from gastos.extraction.schema import Extraction, ParsedQuery
from gastos.services.query_tools import (
    BalancesAnswer,
    QueryService,
    SpendingAnswer,
    TotalsAnswer,
    TransactionsAnswer,
    UnknownCategory,
)
from gastos.services.rates import RateService
from tests.fakes import (
    FakeRateSources,
    FakeRateStore,
    FakeReportStore,
    FakeTransactionStore,
    make_user,
)

CARACAS = ZoneInfo("America/Caracas")
NOW = datetime(2026, 10, 31, 19, tzinfo=UTC)  # sábado 15:00 en Caracas
NOW_LOCAL = NOW.astimezone(CARACAS)
USER = make_user(onboarded=True)  # Bs con tasa paralela
D = Decimal


def rate(currency: QuotedCurrency, source: RateSource, usd: str, age_h: int = 0) -> Rate:
    return Rate(currency, source, D(usd), NOW - timedelta(hours=age_h))


def rates(*items: Rate) -> RateService:
    unused = RuntimeError("no se refresca en estas pruebas")
    sources = FakeRateSources(dolarapi=unused, p2p=unused, cop=unused, usdt=unused)
    return RateService(FakeRateStore(*items), sources, timedelta(hours=6), clock=lambda: NOW)


def query(**fields: Any) -> ParsedQuery:
    return ParsedQuery.model_validate(fields)


def service(store: FakeReportStore, *items: Rate) -> QueryService:
    return QueryService(store, FakeTransactionStore(), rates(*items))


async def test_gasto_por_categoria_usa_este_mes_por_defecto() -> None:
    store = FakeReportStore()
    answer = await service(store).answer(USER, query(tool="spending_by_category"), NOW_LOCAL)
    assert isinstance(answer, SpendingAnswer)
    _, args = store.calls[0]
    assert (args["start"], args["end"]) == (
        datetime(2026, 10, 1, tzinfo=CARACAS),
        datetime(2026, 11, 1, tzinfo=CARACAS),
    )


async def test_totales_con_categoria_y_periodo() -> None:
    store = FakeReportStore(totals=[CurrencyTotal("VES", D(1500), D("1.5"), 3)])
    answer = await service(store).answer(
        USER,
        query(tool="totals", period="this_week", kind="expense", category="Comida"),
        NOW_LOCAL,
    )
    assert isinstance(answer, TotalsAnswer)
    _, args = store.calls[0]
    # La categoría se normaliza al nombre exacto y la semana va de lunes a lunes.
    assert args["category"] == "comida"
    assert args["start"] == datetime(2026, 10, 26, tzinfo=CARACAS)
    assert answer.total_usd == D("1.5")


async def test_categoria_desconocida_no_se_adivina() -> None:
    store = FakeReportStore()
    answer = await service(store).answer(
        USER, query(tool="totals", kind="expense", category="mascotas"), NOW_LOCAL
    )
    assert isinstance(answer, UnknownCategory)
    assert "comida" in answer.available and "salario" not in answer.available
    assert store.calls == []  # sin categoría válida no se consulta nada


async def test_mes_sin_numero_cae_en_este_mes() -> None:
    store = FakeReportStore()
    await service(store).answer(USER, query(tool="totals", period="month"), NOW_LOCAL)
    assert store.calls[0][1]["start"] == datetime(2026, 10, 1, tzinfo=CARACAS)


async def test_ultimos_movimientos_por_defecto() -> None:
    store = FakeReportStore()
    answer = await service(store).answer(
        USER, query(tool="list_transactions", currency="VES"), NOW_LOCAL
    )
    assert isinstance(answer, TransactionsAnswer)
    _, args = store.calls[0]
    assert (args["limit"], args["currency"], args["kind"]) == (10, "VES", None)
    assert args["start"].year == 2000  # desde siempre


BALANCES = [
    AccountBalance("banesco", "VES", D(1000)),
    AccountBalance("efectivo COP", "COP", D(0)),
    AccountBalance("efectivo USD", "USD", D(20)),
    AccountBalance("wallet USDT", "USDT", D(-50)),
]


async def test_saldos_sin_usd_si_no_se_pide() -> None:
    answer = await service(FakeReportStore(balances=BALANCES)).answer(
        USER, query(tool="account_balances", period="last_month"), NOW_LOCAL
    )
    assert isinstance(answer, BalancesAnswer)
    assert answer.total_usd is None and answer.rates == []


async def test_saldos_en_usd_con_las_tasas_vigentes() -> None:
    answer = await service(
        FakeReportStore(balances=BALANCES),
        rate("VES", "parallel", "0.001"),
        rate("USDT", "coingecko", "0.999", age_h=8),
    ).answer(USER, query(tool="account_balances", in_usd=True), NOW_LOCAL)
    assert isinstance(answer, BalancesAnswer)
    # 1000 Bs × 0,001 + 20 USD − 50 USDT × 0,999; el COP en 0 no necesita tasa.
    assert answer.total_usd == D("-28.950000")
    assert [c.rate.currency for c in answer.rates] == ["VES", "USDT"]
    assert answer.rates[1].stale
    assert answer.missing_rates == []


async def test_saldo_sin_tasa_queda_fuera_del_total() -> None:
    answer = await service(
        FakeReportStore(balances=BALANCES), rate("USDT", "coingecko", "1")
    ).answer(USER, query(tool="account_balances", in_usd=True), NOW_LOCAL)
    assert isinstance(answer, BalancesAnswer)
    assert answer.total_usd == D("-30.000000")
    assert answer.missing_rates == ["VES"]


@pytest.mark.parametrize("tool", ["spending_by_category", "totals", "account_balances"])
def test_el_esquema_rechaza_periodos_inventados(tool: str) -> None:
    with pytest.raises(ValueError):
        Extraction.model_validate(
            {"intent": "query", "confidence": 1, "query": {"tool": tool, "period": "2026-10"}}
        )
