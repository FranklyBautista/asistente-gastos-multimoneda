"""Caso de uso: topes por categoría (Fase 12, ADR 0017).

«No quiero gastar más de 100 dólares al mes en comida» fija un tope; «quita el tope de ocio»
lo quita; «¿cómo voy con mis topes?» o /topes muestra lo gastado contra cada uno. Los topes
van en USD: si se dicen en otra moneda, se convierten con la tasa vigente del usuario y se
confirma el valor guardado.

Lo gastado sale de las mismas consultas que el resto del chat (snapshot en USD de cada gasto);
ninguna cifra pasa por el LLM.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Final, Literal, Protocol
from uuid import UUID
from zoneinfo import ZoneInfo

from gastos.domain.account import Category
from gastos.domain.budget import (
    Budget,
    BudgetDraft,
    BudgetProgress,
    days_left_in_month,
    month_window,
    suggested_limit,
)
from gastos.domain.conversion import Rate
from gastos.domain.currency import Currency
from gastos.domain.debt import DEBT_CATEGORIES
from gastos.domain.money import format_money
from gastos.domain.periods import resolve_range
from gastos.domain.reports import CategoryTotal
from gastos.domain.user import User
from gastos.services.outcomes import Ask
from gastos.services.query_tools import UnknownCategory
from gastos.services.rates import CurrentRate

CENTS: Final = Decimal("0.01")
SUGGESTION_MONTHS: Final = 3
ASK_CATEGORY: Final = (
    "¿En qué categoría quieres el tope? Por ejemplo: «no quiero gastar más de 100 dólares al "
    "mes en comida»."
)


class BudgetStore(Protocol):
    """Lo implementa db.BudgetRepository."""

    async def active(self, user_id: UUID) -> list[Budget]: ...
    async def set(
        self, user_id: UUID, category: Category, limit_usd: Decimal, raw_text: str | None
    ) -> tuple[Budget, Budget | None]: ...
    async def remove(self, user_id: UUID, category: Category) -> Budget | None: ...
    async def undo(self, user_id: UUID, budget_id: UUID) -> bool: ...


class SpendingReports(Protocol):
    """Lo implementa db.ReportRepository."""

    async def spending_by_category(
        self, user_id: UUID, start: datetime, end: datetime, currency: Currency | None
    ) -> list[CategoryTotal]: ...
    async def first_movement_at(self, user_id: UUID) -> datetime | None: ...


class CategorySource(Protocol):
    """Lo implementa db.TransactionRepository."""

    async def categories(self, user_id: UUID) -> list[Category]: ...


class UserRates(Protocol):
    """Lo implementa services.RateService."""

    async def for_user(
        self, user: User, currency: Literal["VES", "COP", "USDT"]
    ) -> CurrentRate: ...


# ---- Resultados que el chat convierte en mensajes ----


@dataclass(frozen=True, slots=True)
class BudgetSaved:
    progress: BudgetProgress  # el tope nuevo con lo gastado este mes
    replaced: Budget | None
    converted_from: tuple[Decimal, Currency] | None  # lo que dijo, si no fue en USD
    rate: Rate | None  # la tasa de esa conversión
    stale_rate: bool = False


@dataclass(frozen=True, slots=True)
class BudgetRemoved:
    budget: Budget


@dataclass(frozen=True, slots=True)
class NoBudget:
    category: str


@dataclass(frozen=True, slots=True)
class BudgetStatus:
    rows: list[BudgetProgress]  # por categoría
    days_left: int


BudgetOutcome = BudgetSaved | BudgetRemoved | NoBudget | UnknownCategory | Ask


def spent_by_category(rows: list[CategoryTotal]) -> dict[str, Decimal]:
    """Suma por categoría el snapshot en USD de cada moneda."""
    spent: dict[str, Decimal] = {}
    for row in rows:
        spent[row.category] = spent.get(row.category, Decimal(0)) + row.amount_usd
    return spent


class BudgetService:
    def __init__(
        self,
        store: BudgetStore,
        reports: SpendingReports,
        categories: CategorySource,
        rates: UserRates,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._store = store
        self._reports = reports
        self._categories = categories
        self._rates = rates
        self._clock = clock

    def _now_local(self, user: User) -> datetime:
        return self._clock().astimezone(ZoneInfo(user.timezone))

    async def apply(self, user: User, draft: BudgetDraft, raw_text: str) -> BudgetOutcome:
        """Fija o quita un tope según lo que pidió el mensaje."""
        if draft.category is None:
            return Ask(ASK_CATEGORY)
        category = await self._find_category(user, draft.category)
        if isinstance(category, UnknownCategory):
            return category
        if draft.remove:
            removed = await self._store.remove(user.id, category)
            return BudgetRemoved(removed) if removed else NoBudget(category.name)
        if draft.amount is None:
            return Ask(await self._ask_amount(user, category.name))

        limit, converted, rate, stale = await self._to_usd(user, draft.amount, draft.currency)
        budget, replaced = await self._store.set(user.id, category, limit, raw_text)
        progress = (await self._progress(user, [budget]))[0]
        return BudgetSaved(progress, replaced, converted, rate, stale)

    async def status(self, user: User) -> BudgetStatus:
        budgets = await self._store.active(user.id)
        return BudgetStatus(
            await self._progress(user, budgets), days_left_in_month(self._now_local(user))
        )

    async def progress(self, user: User) -> list[BudgetProgress]:
        """Lo gastado contra cada tope vigente (lo usa el contexto al anotar)."""
        return await self._progress(user, await self._store.active(user.id))

    async def undo(self, user: User, budget_id: UUID) -> bool:
        return await self._store.undo(user.id, budget_id)

    async def _progress(self, user: User, budgets: list[Budget]) -> list[BudgetProgress]:
        if not budgets:
            return []
        now_local = self._now_local(user)
        start, end = month_window(now_local)
        spent = spent_by_category(
            await self._reports.spending_by_category(user.id, start, end, None)
        )
        days_left = days_left_in_month(now_local)
        return [BudgetProgress(b, spent.get(b.category, Decimal(0)), days_left) for b in budgets]

    async def _find_category(self, user: User, name: str) -> Category | UnknownCategory:
        """Una categoría de gasto por su nombre exacto; sin coincidencia no se adivina."""
        candidates = [
            c
            for c in await self._categories.categories(user.id)
            if c.kind == "expense" and c.name not in DEBT_CATEGORIES
        ]
        wanted = name.strip().casefold()
        for category in candidates:
            if category.name.casefold() == wanted:
                return category
        return UnknownCategory(name, sorted(c.name for c in candidates))

    async def _ask_amount(self, user: User, category: str) -> str:
        question = f"¿Cuánto quieres gastar como máximo al mes en {category}?"
        suggestion = await self._suggestion(user, category)
        if suggestion is not None:
            amount = format_money(suggestion, "USD")
            question += f" En los últimos meses gastaste unos {amount} al mes en eso."
        return question

    async def _suggestion(self, user: User, category: str) -> Decimal | None:
        """El promedio de los últimos meses completos en que ya anotaba."""
        first = await self._reports.first_movement_at(user.id)
        if first is None:
            return None
        now_local = self._now_local(user)
        month = resolve_range("this_month", now_local)
        totals: list[Decimal] = []
        for _ in range(SUGGESTION_MONTHS):
            month = resolve_range("last_month", month.start)
            if month.end <= first:
                break  # todavía no anotaba ese mes
            rows = await self._reports.spending_by_category(user.id, month.start, month.end, None)
            totals.append(spent_by_category(rows).get(category, Decimal(0)))
        return suggested_limit(totals)

    async def _to_usd(
        self, user: User, amount: Decimal, currency: Currency | None
    ) -> tuple[Decimal, tuple[Decimal, Currency] | None, Rate | None, bool]:
        """El tope en USD; sin moneda se entiende USD, la unidad de los topes."""
        if currency is None or currency == "USD":
            return amount.quantize(CENTS, rounding=ROUND_HALF_UP), None, None, False
        current = await self._rates.for_user(user, currency)
        usd = (amount * current.rate.usd_per_unit).quantize(CENTS, rounding=ROUND_HALF_UP)
        return max(usd, CENTS), (amount, currency), current.rate, current.stale
