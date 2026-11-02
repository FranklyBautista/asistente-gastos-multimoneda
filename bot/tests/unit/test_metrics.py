"""Métricas del resumen semanal y comprobación de cifras: reglas puras."""

from datetime import UTC, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from gastos.domain.conversion import Rate
from gastos.domain.metrics import (
    bolivar_power,
    percent_change,
    top_category,
    week_window,
    weekly_metrics,
)
from gastos.domain.numbers import numbers_in, parse_local_number, unknown_numbers
from gastos.domain.reports import CategoryTotal, CurrencyTotal

CARACAS = ZoneInfo("America/Caracas")
D = Decimal


def test_la_semana_va_del_lunes_hasta_ahora_y_se_compara_a_la_misma_altura() -> None:
    wednesday = datetime(2026, 10, 28, 15, 30, tzinfo=CARACAS)
    window = week_window(wednesday)
    assert window.start == datetime(2026, 10, 26, tzinfo=CARACAS)
    assert window.end == wednesday
    assert window.previous_start == datetime(2026, 10, 19, tzinfo=CARACAS)
    assert window.previous_end == datetime(2026, 10, 21, 15, 30, tzinfo=CARACAS)


@pytest.mark.parametrize(
    ("new", "old", "expected"),
    [("14", "10", D("40.0")), ("5", "10", D("-50.0")), ("1", "3", D("-66.7")), ("5", "0", None)],
)
def test_variacion_porcentual(new: str, old: str, expected: Decimal | None) -> None:
    assert percent_change(D(new), D(old)) == expected


def test_la_categoria_principal_suma_sus_monedas_en_usd() -> None:
    rows = [
        CategoryTotal("transporte", "COP", D(40000), D(10), 2),
        CategoryTotal("comida", "VES", D(2000), D(5), 1),
        CategoryTotal("comida", "USD", D(7), D(7), 1),
    ]
    top = top_category(rows, D(22))
    assert top is not None
    assert (top.name, top.amount_usd, top.share_pct) == ("comida", D(12), D("54.5"))
    assert top.amounts == [("USD", D(7)), ("VES", D(2000))]
    assert top_category([], D(0)) is None


def test_poder_adquisitivo_del_bolivar_sobre_el_saldo() -> None:
    start = Rate("VES", "parallel", D("0.0025"), datetime(2026, 10, 26, tzinfo=UTC))
    now = Rate("VES", "parallel", D("0.002"), datetime(2026, 11, 1, tzinfo=UTC))
    power = bolivar_power("parallel", start, now, D(10000))
    assert power.change_pct == D("-20.0")
    assert (power.value_start_usd, power.value_now_usd) == (D(25), D(20))
    assert power.value_change_usd == D(-5)


def test_poder_adquisitivo_exige_tasas_del_bolivar() -> None:
    usdt = Rate("USDT", "coingecko", D("0.999"), datetime(2026, 11, 1, tzinfo=UTC))
    with pytest.raises(ValueError):
        bolivar_power("parallel", usdt, usdt, D(1))


def test_metricas_de_la_semana() -> None:
    window = week_window(datetime(2026, 11, 1, 18, tzinfo=CARACAS))
    metrics = weekly_metrics(
        window,
        expenses=[CurrencyTotal("COP", D(20000), D(5), 1), CurrencyTotal("VES", D(4000), D(9), 3)],
        income=[CurrencyTotal("USDT", D(200), D("199.8"), 1)],
        previous_expenses=[CurrencyTotal("USD", D(10), D(10), 2)],
        categories=[CategoryTotal("comida", "VES", D(4000), D(9), 3)],
        bolivar=None,
    )
    assert (metrics.expenses_usd, metrics.income_usd) == (D(14), D("199.8"))
    assert metrics.expense_change_pct == D("40.0")
    assert metrics.movements == 5 and metrics.has_activity
    assert metrics.top_category is not None and metrics.top_category.share_pct == D("64.3")


# ---- Cifras del texto del LLM ----


def test_extrae_los_numeros_tal_como_aparecen() -> None:
    assert numbers_in("Gastaste 1.200,50 Bs (12 %) el 26/10.") == ["1.200,50", "12", "26", "10"]


@pytest.mark.parametrize(
    ("token", "expected"),
    [
        ("1.200,50", D("1200.50")),
        ("20.000", D(20000)),
        ("64,3", D("64.3")),
        ("7", D(7)),
        ("1.2", None),  # no es un número de miles válido
        ("1,2,3", None),
    ],
)
def test_lee_numeros_a_la_venezolana(token: str, expected: Decimal | None) -> None:
    assert parse_local_number(token) == expected


def test_acepta_las_cifras_de_las_metricas_aunque_cambie_el_formato() -> None:
    allowed = ["Gastaste 1.200,00 Bs (≈ 14,00 USD).", "📊 Tu semana · 26/10–01/11"]
    text = "Esta semana (26/10 al 1/11) se te fueron 1.200 Bs, unos 14 USD."
    assert unknown_numbers(text, allowed) == []


def test_rechaza_cifras_inventadas() -> None:
    allowed = ["Gastaste 1.200,00 Bs (≈ 14,00 USD)."]
    assert unknown_numbers("Gastaste 1.250 Bs, unos 14,5 USD.", allowed) == ["1.250", "14,5"]
