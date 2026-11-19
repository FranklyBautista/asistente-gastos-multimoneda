"""Topes por categoría (Fase 12, ADR 0017): reglas puras.

Un tope es cuánto quieres gastar como máximo al mes en una categoría de gasto, en USD. Se
compara con la suma de los snapshots en USD de los gastos (ADR 0002), así no se queda viejo
cada vez que sube el dólar. El mes es el calendario de la zona horaria del usuario.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal
from typing import Final, Literal
from uuid import UUID

from gastos.domain.currency import Currency
from gastos.domain.periods import resolve_range

# Desde qué fracción del tope se avisa que va cerca (la investigación no fija un umbral;
# 80 % es el habitual en las apps y deja margen para reaccionar).
NEAR_SHARE: Final = Decimal("0.8")
# El tope sugerido se redondea hacia arriba a múltiplos de 5 USD: es una propuesta, no una
# cifra exacta.
SUGGESTION_STEP: Final = Decimal(5)
PCT_SCALE: Final = Decimal(1)

BudgetState = Literal["ok", "near", "over"]


@dataclass(frozen=True, slots=True)
class BudgetDraft:
    """Lo que pidió el usuario: «tope de 100 dólares en comida» o «quita el tope de ocio»."""

    category: str | None
    amount: Decimal | None  # None: preguntar, con un tope sugerido
    currency: Currency | None  # None: USD, la unidad de los topes
    remove: bool = False


@dataclass(frozen=True, slots=True)
class Budget:
    id: UUID
    category: str
    limit_usd: Decimal


@dataclass(frozen=True, slots=True)
class BudgetProgress:
    budget: Budget
    spent_usd: Decimal  # suma de snapshots en USD del mes en curso
    days_left: int  # días que quedan en el mes, contando hoy

    @property
    def remaining_usd(self) -> Decimal:
        return self.budget.limit_usd - self.spent_usd

    @property
    def used_pct(self) -> Decimal:
        """Qué % del tope se lleva, sin decimales."""
        return (self.spent_usd / self.budget.limit_usd * 100).quantize(
            PCT_SCALE, rounding=ROUND_HALF_UP
        )

    @property
    def state(self) -> BudgetState:
        if self.spent_usd > self.budget.limit_usd:
            return "over"
        if self.spent_usd >= self.budget.limit_usd * NEAR_SHARE:
            return "near"
        return "ok"


def month_window(now_local: datetime) -> tuple[datetime, datetime]:
    """Inicio del mes local en curso y ahora (el rango de un tope)."""
    return resolve_range("this_month", now_local).start, now_local


def days_left_in_month(now_local: datetime) -> int:
    """Días que quedan del mes, contando hoy: el 30 de noviembre queda 1."""
    end = resolve_range("this_month", now_local).end
    return (end.date() - now_local.date()).days


def suggested_limit(monthly_spent_usd: list[Decimal]) -> Decimal | None:
    """Tope propuesto: el promedio de los meses dados, redondeado hacia arriba a 5 USD.

    Los meses que recibe son meses completos con historial; None si no hay ninguno o si no
    gastó nada en esa categoría.
    """
    if not monthly_spent_usd:
        return None
    average = sum(monthly_spent_usd, Decimal(0)) / len(monthly_spent_usd)
    if average <= 0:
        return None
    steps = (average / SUGGESTION_STEP).to_integral_value(rounding=ROUND_CEILING)
    return steps * SUGGESTION_STEP
