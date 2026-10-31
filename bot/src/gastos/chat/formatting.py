"""Formato de números y tiempos para los mensajes del bot."""

from datetime import timedelta
from decimal import Decimal
from typing import Final

from gastos.domain.currency import Currency

# Decimales al mostrar: los pesos no se usan con centavos.
DECIMALS: Final[dict[Currency, int]] = {"VES": 2, "COP": 0, "USD": 2, "USDT": 2}
SYMBOLS: Final[dict[Currency, str]] = {"VES": "Bs", "COP": "COP", "USD": "USD", "USDT": "USDT"}


def format_number(value: Decimal, decimals: int) -> str:
    """1234.5 → "1.234,50", como se escriben los montos en Venezuela y Colombia."""
    return f"{value:,.{decimals}f}".replace(",", "_").replace(".", ",").replace("_", ".")


def format_age(delta: timedelta) -> str:
    hours = int(delta.total_seconds() // 3600)
    if hours >= 48:
        return f"{hours // 24} días"
    if hours >= 1:
        return f"{hours} h"
    return f"{max(1, int(delta.total_seconds() // 60))} min"


def format_money(amount: Decimal, currency: Currency) -> str:
    """70 VES → "70,00 Bs"; 20000 COP → "20.000 COP"."""
    return f"{format_number(amount, DECIMALS[currency])} {SYMBOLS[currency]}"
