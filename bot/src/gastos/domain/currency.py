"""Monedas soportadas y fuentes de tasa del bolívar (ADR 0002)."""

from typing import Final, Literal

from gastos.domain.errors import InvalidPreference

Currency = Literal["VES", "COP", "USD", "USDT"]
VesRateSource = Literal["bcv", "parallel", "p2p"]

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
