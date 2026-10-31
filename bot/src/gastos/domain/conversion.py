"""Conversión a USD (ADR 0002): toda tasa es usd_per_unit, los USD que vale 1 unidad."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import ROUND_HALF_EVEN, Decimal
from typing import Literal

from gastos.domain.currency import Currency, QuotedCurrency, RateSource

# Escalas de las columnas numeric(20,10) y numeric(20,6) de la base de datos.
RATE_SCALE = Decimal("1e-10")
USD_SCALE = Decimal("1e-6")
ONE = Decimal(1)


class CurrencyMismatch(ValueError):
    """Monto convertido con la tasa de otra moneda: es un bug, no un error del usuario."""


@dataclass(frozen=True, slots=True)
class Rate:
    """Cuántos USD vale 1 unidad de la moneda, según una fuente y en un momento dado."""

    currency: QuotedCurrency
    source: RateSource
    usd_per_unit: Decimal
    fetched_at: datetime

    def __post_init__(self) -> None:
        if not (self.usd_per_unit.is_finite() and self.usd_per_unit > 0):
            raise ValueError(f"usd_per_unit debe ser positivo: {self.usd_per_unit}")
        if self.fetched_at.tzinfo is None:
            raise ValueError("fetched_at debe llevar zona horaria (UTC)")


@dataclass(frozen=True, slots=True)
class UsdSnapshot:
    """Lo que se guarda junto a un movimiento: la tasa usada y el monto equivalente en USD."""

    usd_per_unit: Decimal
    rate_source: RateSource | Literal["pivot"]
    amount_usd: Decimal


def usd_per_unit_from(price: Decimal, *, quote_usd_per_unit: Decimal = ONE) -> Decimal:
    """Convierte una cotización "unidades por 1 de otra moneda" a usd_per_unit.

    Las fuentes publican al revés (887,30 Bs por dólar); aquí se invierte una sola vez.
    Si la cotización no es contra USD (Bs por USDT en P2P), `quote_usd_per_unit` es la
    tasa de esa otra moneda.
    """
    if not (price.is_finite() and price > 0):
        raise ValueError(f"la cotización debe ser positiva: {price}")
    usd_per_unit = (quote_usd_per_unit / price).quantize(RATE_SCALE, rounding=ROUND_HALF_EVEN)
    if usd_per_unit <= 0:
        raise ValueError(f"cotización fuera de la escala de la base de datos: {price}")
    return usd_per_unit


def units_per_usd(rate: Rate) -> Decimal:
    """Lo inverso, solo para mostrar: cuántas unidades de la moneda da 1 USD."""
    return ONE / rate.usd_per_unit


def to_usd(amount: Decimal, currency: Currency, rate: Rate | None) -> UsdSnapshot:
    """Snapshot en USD de un monto. USD es el pivote y va sin tasa; el resto exige la suya."""
    if currency == "USD":
        if rate is not None:
            raise CurrencyMismatch(f"USD no lleva tasa y llegó una de {rate.currency}")
        usd_per_unit, source = ONE, "pivot"
    else:
        if rate is None or rate.currency != currency:
            got = rate.currency if rate else "ninguna"
            raise CurrencyMismatch(f"monto en {currency} con tasa de {got}")
        usd_per_unit, source = rate.usd_per_unit, rate.source
    amount_usd = (amount * usd_per_unit).quantize(USD_SCALE, rounding=ROUND_HALF_EVEN)
    return UsdSnapshot(usd_per_unit=usd_per_unit, rate_source=source, amount_usd=amount_usd)


def is_stale(rate: Rate, now: datetime, max_age: timedelta) -> bool:
    """Una tasa es vieja si su fuente lleva más de `max_age` sin responder."""
    return now - rate.fetched_at > max_age
