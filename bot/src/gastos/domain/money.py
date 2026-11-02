"""Cómo se escriben los montos: precisión por moneda y formato de Venezuela y Colombia.

Vive en el dominio porque lo usan el chat (plantillas) y los servicios (las cifras que se le
pasan al LLM en el resumen semanal deben escribirse igual que en el texto final).
"""

from decimal import Decimal
from typing import Final

from gastos.domain.currency import Currency

# Decimales al mostrar: los pesos no se usan con centavos.
DECIMALS: Final[dict[Currency, int]] = {"VES": 2, "COP": 0, "USD": 2, "USDT": 2}
SYMBOLS: Final[dict[Currency, str]] = {"VES": "Bs", "COP": "COP", "USD": "USD", "USDT": "USDT"}


def format_number(value: Decimal, decimals: int) -> str:
    """1234.5 → "1.234,50", como se escriben los montos en Venezuela y Colombia."""
    return f"{value:,.{decimals}f}".replace(",", "_").replace(".", ",").replace("_", ".")


def format_money(amount: Decimal, currency: Currency) -> str:
    """70 VES → "70,00 Bs"; 20000 COP → "20.000 COP"."""
    return f"{format_number(amount, DECIMALS[currency])} {SYMBOLS[currency]}"
