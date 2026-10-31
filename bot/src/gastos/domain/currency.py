"""Monedas soportadas y fuentes de tasa del bolívar (ADR 0002)."""

from typing import Final, Literal

from gastos.domain.errors import InvalidPreference

Currency = Literal["VES", "COP", "USD", "USDT"]
QuotedCurrency = Literal["VES", "COP", "USDT"]  # USD es el pivote: no tiene tasa propia
VesRateSource = Literal["bcv", "parallel", "p2p"]
RateSource = Literal["bcv", "parallel", "p2p", "fx", "coingecko"]

CURRENCIES: Final[tuple[Currency, ...]] = ("VES", "COP", "USD", "USDT")
VES_RATE_SOURCES: Final[tuple[VesRateSource, ...]] = ("bcv", "parallel", "p2p")


def parse_currency(value: str) -> Currency:
    """Valida un código de moneda interno; lanza InvalidPreference si no existe."""
    if value not in CURRENCIES:
        raise InvalidPreference("currency", value)
    return value


def parse_ves_rate_source(value: str) -> VesRateSource:
    """Valida una fuente de tasa de Bs; lanza InvalidPreference si no existe."""
    if value not in VES_RATE_SOURCES:
        raise InvalidPreference("ves_rate_source", value)
    return value


def rate_source_for(currency: QuotedCurrency, ves_rate_source: VesRateSource) -> RateSource:
    """Fuente de la tasa de una moneda; la del bolívar es preferencia del usuario."""
    if currency == "VES":
        return ves_rate_source
    if currency == "COP":
        return "fx"
    return "coingecko"
