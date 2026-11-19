"""Caso de uso: la línea de contexto que acompaña a cada gasto anotado (Fase 12, ADR 0017).

«✅ Gasto · 15,00 USD · comida» sale con una línea más que dice cómo vas en esa categoría:
- con tope: «comida: llevas 80,00 USD de 100,00 este mes · quedan 12 días»;
- sin tope, si ya anotabas la semana pasada: «comida esta semana: 62,00 USD · la semana
  pasada a esta altura: 50,00»;
- sin historial, nada.

Mirar los propios números a menudo, en el momento, es lo que mejor respaldo tiene en la
investigación (informe, sección 2). Como mucho dos líneas por mensaje, sin juicios, y se
apaga con /contexto. Si algo falla, la confirmación sale igual sin contexto.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Final, Protocol
from uuid import UUID
from zoneinfo import ZoneInfo

import structlog

from gastos.domain.budget import BudgetProgress
from gastos.domain.currency import Currency
from gastos.domain.debt import DEBT_CATEGORIES
from gastos.domain.metrics import week_window
from gastos.domain.reports import CurrencyTotal
from gastos.domain.transaction import SavedTransaction, TransactionKind
from gastos.domain.user import User

log = structlog.get_logger()

MAX_LINES: Final = 2
# El gasto recién anotado lleva la hora de la base de datos; este margen lo incluye aunque
# los relojes del bot y de la base no coincidan al segundo.
CLOCK_SLACK: Final = timedelta(minutes=1)


class BudgetProgressSource(Protocol):
    """Lo implementa services.BudgetService."""

    async def progress(self, user: User) -> list[BudgetProgress]: ...


class ContextReports(Protocol):
    """Lo implementa db.ReportRepository."""

    async def totals(
        self,
        user_id: UUID,
        kind: TransactionKind,
        start: datetime,
        end: datetime,
        currency: Currency | None,
        category: str | None,
    ) -> list[CurrencyTotal]: ...
    async def first_movement_at(self, user_id: UUID) -> datetime | None: ...


@dataclass(frozen=True, slots=True)
class BudgetLine:
    progress: BudgetProgress


@dataclass(frozen=True, slots=True)
class WeekLine:
    category: str
    week_usd: Decimal  # lo gastado en la categoría desde el lunes, en USD
    previous_usd: Decimal  # la semana pasada a la misma altura


ContextLine = BudgetLine | WeekLine


def _usd(rows: list[CurrencyTotal]) -> Decimal:
    return sum((r.amount_usd for r in rows), Decimal(0))


def expense_categories(saved: Sequence[SavedTransaction]) -> list[str]:
    """Las categorías de gasto del mensaje, en orden y sin repetir (sin las de deudas)."""
    seen: list[str] = []
    for tx in saved:
        if tx.kind == "expense" and tx.category not in DEBT_CATEGORIES and tx.category not in seen:
            seen.append(tx.category)
    return seen


class ContextService:
    def __init__(
        self,
        budgets: BudgetProgressSource,
        reports: ContextReports,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._budgets = budgets
        self._reports = reports
        self._clock = clock

    async def lines(self, user: User, saved: Sequence[SavedTransaction]) -> list[ContextLine]:
        """Hasta dos líneas de contexto; nunca falla (sin contexto si algo sale mal)."""
        if not user.context_replies:
            return []
        categories = expense_categories(saved)
        if not categories:
            return []
        try:
            return await self._lines(user, categories)
        except Exception as exc:  # el contexto es un extra: el gasto ya quedó anotado
            log.warning("context_failed", error=type(exc).__name__)
            return []

    async def _lines(self, user: User, categories: list[str]) -> list[ContextLine]:
        by_category = {p.budget.category: p for p in await self._budgets.progress(user)}
        with_budget: list[ContextLine] = [
            BudgetLine(by_category[c]) for c in categories if c in by_category
        ]
        lines = with_budget[:MAX_LINES]
        rest = [c for c in categories if c not in by_category]
        if len(lines) >= MAX_LINES or not rest:
            return lines

        now = self._clock() + CLOCK_SLACK
        window = week_window(now.astimezone(ZoneInfo(user.timezone)))
        first = await self._reports.first_movement_at(user.id)
        if first is None or first >= window.previous_start:
            return lines  # la semana pasada todavía no anotaba: no hay con qué comparar
        for category in rest[: MAX_LINES - len(lines)]:
            week = await self._reports.totals(
                user.id, "expense", window.start, window.end, None, category
            )
            previous = await self._reports.totals(
                user.id, "expense", window.previous_start, window.previous_end, None, category
            )
            lines.append(WeekLine(category, _usd(week), _usd(previous)))
        return lines
