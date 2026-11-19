"""Colchón en días (Fase 12, ADR 0017): cuánto duraría lo que tienes si no entrara más dinero.

colchón = saldo total en USD (tasas vigentes) / gasto diario promedio en USD

El gasto diario es lo gastado en los últimos 90 días entre esos días o, si el usuario lleva
menos tiempo anotando, entre los días desde su primer movimiento. Con menos de dos semanas
de historial el promedio no dice nada y no se calcula. Lo que te deben no cuenta: no es
dinero disponible hasta que te lo paguen.

La web hace la misma cuenta con la función SQL `spending_pace` (migración de la Fase 12).
"""

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_FLOOR, ROUND_HALF_UP, Decimal
from typing import Final, Literal

WINDOW_DAYS: Final = 90
MIN_HISTORY_DAYS: Final = 14
# Escalones: el primero que se pasa es el siguiente objetivo. Un mes de gastos es el que
# más separa a quien pasa apuros de quien no (informe de investigación, sección 1).
STEPS: Final = (14, 30, 60, 90)
CENTS: Final = Decimal("0.01")

RunwayGap = Literal["no_history", "short_history", "no_expenses"]


@dataclass(frozen=True, slots=True)
class Runway:
    available_usd: Decimal
    daily_spend_usd: Decimal  # redondeado a centavos
    days: int
    window_days: int  # cuántos días se usaron para el promedio

    @property
    def next_step(self) -> int | None:
        """El siguiente escalón por alcanzar, o None si ya pasó el último."""
        return next((s for s in STEPS if s > self.days), None)


@dataclass(frozen=True, slots=True)
class RunwayUnknown:
    reason: RunwayGap
    history_days: int = 0


def window_days(first_day: date | None, today: date, max_days: int = WINDOW_DAYS) -> int | None:
    """Días de historial que entran en el promedio; None si no hay ningún movimiento."""
    if first_day is None:
        return None
    return max(1, min((today - first_day).days + 1, max_days))


def runway(
    available_usd: Decimal, expenses_usd: Decimal, days: int | None
) -> Runway | RunwayUnknown:
    """El colchón, o por qué todavía no se puede calcular."""
    if days is None:
        return RunwayUnknown("no_history")
    if days < MIN_HISTORY_DAYS:
        return RunwayUnknown("short_history", days)
    if expenses_usd <= 0:
        return RunwayUnknown("no_expenses", days)
    daily = expenses_usd / days
    covered = max(available_usd, Decimal(0)) / daily
    return Runway(
        available_usd=available_usd,
        daily_spend_usd=daily.quantize(CENTS, rounding=ROUND_HALF_UP),
        days=int(covered.to_integral_value(rounding=ROUND_FLOOR)),
        window_days=days,
    )
