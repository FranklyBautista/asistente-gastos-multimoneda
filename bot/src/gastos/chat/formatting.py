"""Formato de números y tiempos para los mensajes del bot.

El formato de montos vive en `domain.money` (también lo usa el resumen semanal); aquí se
reexporta para los handlers.
"""

from datetime import timedelta

from gastos.domain.money import DECIMALS, SYMBOLS, format_money, format_number

__all__ = ["DECIMALS", "SYMBOLS", "format_age", "format_money", "format_number"]


def format_age(delta: timedelta) -> str:
    hours = int(delta.total_seconds() // 3600)
    if hours >= 48:
        return f"{hours // 24} días"
    if hours >= 1:
        return f"{hours} h"
    return f"{max(1, int(delta.total_seconds() // 60))} min"
