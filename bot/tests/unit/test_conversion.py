from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from gastos.domain.conversion import (
    CurrencyMismatch,
    Rate,
    is_stale,
    to_usd,
    units_per_usd,
    usd_per_unit_from,
)
from gastos.domain.currency import QuotedCurrency, RateSource, rate_source_for

NOW = datetime(2026, 10, 27, 12, tzinfo=UTC)


def rate(currency: QuotedCurrency, usd_per_unit: str, source: RateSource = "fx") -> Rate:
    return Rate(currency, source, Decimal(usd_per_unit), NOW)


def test_invierte_la_cotizacion_de_la_fuente() -> None:
    # Las fuentes dicen "4.000 COP por dólar"; se guarda "0,00025 USD por peso".
    assert usd_per_unit_from(Decimal("4000")) == Decimal("0.00025")
    assert usd_per_unit_from(Decimal("3")) == Decimal("0.3333333333")


def test_cruza_una_cotizacion_que_no_es_contra_usd() -> None:
    # P2P: 1.000 Bs por USDT y 1 USDT = 0,999 USD.
    assert usd_per_unit_from(Decimal("1000"), quote_usd_per_unit=Decimal("0.999")) == Decimal(
        "0.000999"
    )


@pytest.mark.parametrize("price", [Decimal(0), Decimal(-5), Decimal("NaN"), Decimal("1e12")])
def test_rechaza_cotizaciones_invalidas(price: Decimal) -> None:
    with pytest.raises(ValueError):
        usd_per_unit_from(price)


@pytest.mark.parametrize(
    ("currency", "units_per_usd_price"),
    [("VES", "887.302"), ("COP", "3143.42897"), ("USDT", "1.0012")],
)
def test_un_dolar_de_cada_moneda_vale_un_dolar(
    currency: QuotedCurrency, units_per_usd_price: str
) -> None:
    # Si alguien guardara la tasa al revés, esto daría 787.304 USD en vez de 1.
    price = Decimal(units_per_usd_price)
    snapshot = to_usd(price, currency, rate(currency, str(usd_per_unit_from(price))))
    assert snapshot.amount_usd == Decimal("1.000000")


@pytest.mark.parametrize(
    ("amount", "currency", "usd_per_unit", "expected"),
    [
        ("70", "VES", "0.001", "0.070000"),
        ("20000", "COP", "0.00025", "5.000000"),
        ("200", "USDT", "0.9988", "199.760000"),
    ],
)
def test_snapshot_de_las_monedas_con_tasa(
    amount: str, currency: QuotedCurrency, usd_per_unit: str, expected: str
) -> None:
    snapshot = to_usd(Decimal(amount), currency, rate(currency, usd_per_unit, "bcv"))
    assert snapshot.amount_usd == Decimal(expected)
    assert snapshot.usd_per_unit == Decimal(usd_per_unit)
    assert snapshot.rate_source == "bcv"


def test_usd_es_el_pivote() -> None:
    snapshot = to_usd(Decimal("15"), "USD", None)
    assert (snapshot.amount_usd, snapshot.usd_per_unit, snapshot.rate_source) == (
        Decimal("15.000000"),
        Decimal(1),
        "pivot",
    )


def test_redondea_al_centavo_de_la_base_de_datos() -> None:
    snapshot = to_usd(Decimal("1"), "VES", rate("VES", "0.0011270120"))
    assert snapshot.amount_usd == Decimal("0.001127")


@pytest.mark.parametrize(
    ("currency", "with_rate"),
    [("COP", rate("VES", "0.001")), ("VES", None), ("USD", rate("VES", "0.001"))],
)
def test_no_mezcla_monedas(currency: QuotedCurrency, with_rate: Rate | None) -> None:
    with pytest.raises(CurrencyMismatch):
        to_usd(Decimal("10"), currency, with_rate)


def test_un_float_no_entra_en_la_cuenta() -> None:
    with pytest.raises(TypeError):
        to_usd(15.0, "VES", rate("VES", "0.001"))  # pyright: ignore[reportArgumentType]


def test_la_tasa_exige_valor_positivo_y_hora_con_zona() -> None:
    with pytest.raises(ValueError):
        rate("VES", "0")
    with pytest.raises(ValueError):
        Rate("VES", "bcv", Decimal("0.001"), datetime(2026, 10, 27, 12))


def test_unidades_por_dolar_para_mostrar() -> None:
    assert units_per_usd(rate("COP", "0.00025")) == Decimal(4000)


def test_tasa_vieja_segun_su_antiguedad() -> None:
    old = Rate("VES", "bcv", Decimal("0.001"), NOW - timedelta(hours=7))
    fresh = Rate("VES", "bcv", Decimal("0.001"), NOW - timedelta(hours=5))
    assert is_stale(old, NOW, timedelta(hours=6))
    assert not is_stale(fresh, NOW, timedelta(hours=6))


@pytest.mark.parametrize(
    ("currency", "expected"), [("VES", "p2p"), ("COP", "fx"), ("USDT", "coingecko")]
)
def test_fuente_de_cada_moneda(currency: QuotedCurrency, expected: RateSource) -> None:
    assert rate_source_for(currency, "p2p") == expected
