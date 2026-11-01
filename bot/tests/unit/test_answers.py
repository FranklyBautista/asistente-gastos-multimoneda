"""Textos de las respuestas a consultas: por moneda, sin cifras inventadas."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from gastos.chat.answers import (
    balances_text,
    period_text,
    spending_text,
    totals_text,
    transactions_text,
    unknown_category_text,
)
from gastos.domain.conversion import Rate
from gastos.domain.periods import resolve_range
from gastos.domain.reports import AccountBalance, CategoryTotal, CurrencyTotal, TransactionRow
from gastos.services.query_tools import (
    BalancesAnswer,
    SpendingAnswer,
    TotalsAnswer,
    TransactionsAnswer,
    UnknownCategory,
)
from gastos.services.rates import CurrentRate
from tests.fakes import make_user

CARACAS = ZoneInfo("America/Caracas")
NOW = datetime(2026, 10, 31, 19, tzinfo=UTC)
NOW_LOCAL = NOW.astimezone(CARACAS)
USER = make_user(onboarded=True)
D = Decimal
WEEK = resolve_range("this_week", NOW_LOCAL)


def test_periodos_con_fechas() -> None:
    assert period_text(WEEK) == "esta semana (26/10–01/11)"
    assert period_text(resolve_range("today", NOW_LOCAL)) == "hoy (31/10)"
    assert period_text(resolve_range("month", NOW_LOCAL, 9)) == "en septiembre 2026"
    assert period_text(resolve_range("all_time", NOW_LOCAL)) == "desde que empezaste a registrar"


def test_gasto_por_categoria_agrupa_monedas_sin_sumarlas() -> None:
    rows = [
        CategoryTotal("transporte", "COP", D(20000), D(5), 1),
        CategoryTotal("comida", "VES", D(1250), D("1.25"), 2),
        CategoryTotal("comida", "USD", D(3), D(3), 1),
    ]
    text = spending_text(SpendingAnswer(WEEK, rows, None, in_usd=False))
    assert text.splitlines() == [
        "Gastos por categoría · esta semana (26/10–01/11):",
        "• transporte: 20.000 COP",
        "• comida: 1.250,00 Bs · 3,00 USD",
    ]


def test_gasto_por_categoria_en_usd_si_se_pide() -> None:
    rows = [
        CategoryTotal("comida", "VES", D(1250), D("1.25"), 2),
        CategoryTotal("comida", "USD", D(3), D(3), 1),
    ]
    lines = spending_text(SpendingAnswer(WEEK, rows, None, in_usd=True)).splitlines()
    assert lines[1] == "• comida: 1.250,00 Bs · 3,00 USD (≈ 4,25 USD)"
    assert lines[-1] == "Total ≈ 4,25 USD, con la tasa de cada movimiento al registrarlo."


def test_totales_por_moneda() -> None:
    rows = [CurrencyTotal("VES", D(1500), D("1.5"), 3), CurrencyTotal("USD", D(15), D(15), 1)]
    answer = TotalsAnswer(WEEK, "expense", rows, None, "comida", in_usd=False)
    assert totals_text(answer).splitlines() == [
        "Gastos en comida · esta semana (26/10–01/11):",
        "• 1.500,00 Bs (3 movimientos)",
        "• 15,00 USD (1 movimiento)",
    ]


def test_sin_datos_lo_dice() -> None:
    answer = TotalsAnswer(WEEK, "income", [], "USDT", None, in_usd=True)
    assert totals_text(answer) == "No tengo ingresos en USDT registrados esta semana (26/10–01/11)."
    assert spending_text(SpendingAnswer(WEEK, [], None, False)).startswith("No tengo gastos")
    empty = TransactionsAnswer(resolve_range("all_time", NOW_LOCAL), [], None, None, None)
    assert (
        transactions_text(empty, USER) == "No encontré movimientos desde que empezaste a registrar."
    )


def test_saldos_ocultan_las_cuentas_en_cero_y_avisan_tasas() -> None:
    stale = CurrentRate(Rate("USDT", "coingecko", D("0.999"), NOW - timedelta(hours=8)), True)
    rows = [
        AccountBalance("banesco", "VES", D(1000)),
        AccountBalance("efectivo COP", "COP", D(0)),
        AccountBalance("wallet USDT", "USDT", D(-50)),
    ]
    answer = BalancesAnswer(rows, True, D("-48.95"), [stale], ["VES"])
    assert balances_text(answer, NOW).splitlines() == [
        "Saldos:",
        "• banesco: 1.000,00 Bs",
        "• wallet USDT: -50,00 USDT",
        "",
        "Total ≈ -48,95 USD con las tasas de hoy (USDT).",
        "⚠️ La tasa de USDT lleva 8 h sin actualizarse.",
        "⚠️ Sin tasa para Bs: no está incluido en el total.",
    ]


def test_todas_las_cuentas_en_cero() -> None:
    answer = BalancesAnswer([AccountBalance("efectivo USD", "USD", D(0))], False, None, [], [])
    assert balances_text(answer, NOW).startswith("Todas tus cuentas están en 0")


def test_lista_de_movimientos_en_la_hora_del_usuario() -> None:
    rows = [
        # 01:00 UTC del 31 todavía es el 30 en Caracas.
        TransactionRow(
            datetime(2026, 10, 31, 1, tzinfo=UTC), "expense", D(70), "VES", "transporte", "pasaje"
        ),
        TransactionRow(
            datetime(2026, 10, 29, 15, tzinfo=UTC), "income", D(200), "USDT", "otros ingresos", None
        ),
    ]
    answer = TransactionsAnswer(resolve_range("all_time", NOW_LOCAL), rows, None, None, None)
    assert transactions_text(answer, USER).splitlines() == [
        "Últimos movimientos:",
        "• 30/10 · Gasto · 70,00 Bs · transporte · pasaje",
        "• 29/10 · Ingreso · 200,00 USDT · otros ingresos",
    ]


def test_categoria_desconocida() -> None:
    text = unknown_category_text(UnknownCategory("mascotas", ["comida", "ocio"]))
    assert text == (
        "No tengo una categoría «mascotas», así que no puedo filtrar por ella. "
        "Las que hay: comida, ocio."
    )
