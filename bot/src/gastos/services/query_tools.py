"""Caso de uso: responder preguntas sobre las finanzas con datos reales de la base de datos.

El LLM elige la herramienta y sus parámetros (`ParsedQuery`); aquí se resuelven las fechas,
se valida la categoría y se consulta con SQL fijo. Las respuestas no pasan por el LLM: el chat
las arma con plantillas, así que ninguna cifra puede salir inventada.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Final, Literal, Protocol
from uuid import UUID

from gastos.domain.account import Category
from gastos.domain.conversion import USD_SCALE
from gastos.domain.currency import Currency
from gastos.domain.errors import RateUnavailable
from gastos.domain.periods import DateRange, Period, resolve_range
from gastos.domain.reports import AccountBalance, CategoryTotal, CurrencyTotal, TransactionRow
from gastos.domain.transaction import TransactionKind
from gastos.domain.user import User
from gastos.extraction.schema import ParsedQuery
from gastos.services.rates import CurrentRate

DEFAULT_PERIOD: Final[dict[str, Period]] = {
    "spending_by_category": "this_month",
    "totals": "this_month",
    "list_transactions": "all_time",
}
DEFAULT_LIMIT: Final = 10


class ReportStore(Protocol):
    """Lo implementa db.ReportRepository."""

    async def spending_by_category(
        self, user_id: UUID, start: datetime, end: datetime, currency: Currency | None
    ) -> list[CategoryTotal]: ...
    async def totals(
        self,
        user_id: UUID,
        kind: TransactionKind,
        start: datetime,
        end: datetime,
        currency: Currency | None,
        category: str | None,
    ) -> list[CurrencyTotal]: ...
    async def account_balances(self, user_id: UUID) -> list[AccountBalance]: ...
    async def list_transactions(
        self,
        user_id: UUID,
        start: datetime,
        end: datetime,
        kind: TransactionKind | None,
        currency: Currency | None,
        category: str | None,
        limit: int,
    ) -> list[TransactionRow]: ...


class CategorySource(Protocol):
    """Lo implementa db.TransactionRepository."""

    async def categories(self, user_id: UUID) -> list[Category]: ...


class UserRates(Protocol):
    """Lo implementa services.RateService."""

    async def for_user(
        self, user: User, currency: Literal["VES", "COP", "USDT"]
    ) -> CurrentRate: ...


# ---- Respuestas; las vacías se contestan con "no tengo datos" ----


@dataclass(frozen=True, slots=True)
class SpendingAnswer:
    range: DateRange
    rows: list[CategoryTotal]
    currency: Currency | None
    in_usd: bool


@dataclass(frozen=True, slots=True)
class TotalsAnswer:
    range: DateRange
    kind: TransactionKind
    rows: list[CurrencyTotal]
    currency: Currency | None
    category: str | None
    in_usd: bool

    @property
    def total_usd(self) -> Decimal:
        """Suma de los snapshots: lo que valía cada movimiento al registrarse."""
        return sum((r.amount_usd for r in self.rows), Decimal(0))


@dataclass(frozen=True, slots=True)
class BalancesAnswer:
    rows: list[AccountBalance]
    in_usd: bool
    total_usd: Decimal | None  # con las tasas vigentes; None si no se pidió
    rates: list[CurrentRate]  # las tasas usadas para el total en USD
    missing_rates: list[Currency]  # monedas con saldo pero sin tasa: quedan fuera del total


@dataclass(frozen=True, slots=True)
class TransactionsAnswer:
    range: DateRange
    rows: list[TransactionRow]
    kind: TransactionKind | None
    currency: Currency | None
    category: str | None


@dataclass(frozen=True, slots=True)
class UnknownCategory:
    name: str
    available: list[str]


QueryAnswer = SpendingAnswer | TotalsAnswer | BalancesAnswer | TransactionsAnswer | UnknownCategory


class QueryService:
    def __init__(self, store: ReportStore, categories: CategorySource, rates: UserRates) -> None:
        self._store = store
        self._categories = categories
        self._rates = rates

    async def answer(self, user: User, query: ParsedQuery, now_local: datetime) -> QueryAnswer:
        if query.tool == "account_balances":
            return await self._balances(user, query.in_usd)

        category = None
        if query.category:
            found = await self._find_category(user, query.category, query)
            if isinstance(found, UnknownCategory):
                return found
            category = found

        period = query.period or DEFAULT_PERIOD[query.tool]
        if period == "month" and query.month is None:
            period = "this_month"  # el LLM dijo "un mes" sin decir cuál
        date_range = resolve_range(period, now_local, query.month, query.year)
        start, end = date_range.start, date_range.end

        if query.tool == "spending_by_category":
            rows = await self._store.spending_by_category(user.id, start, end, query.currency)
            return SpendingAnswer(date_range, rows, query.currency, query.in_usd)
        if query.tool == "totals":
            kind = query.kind or "expense"
            rows = await self._store.totals(user.id, kind, start, end, query.currency, category)
            return TotalsAnswer(date_range, kind, rows, query.currency, category, query.in_usd)
        limit = query.limit or DEFAULT_LIMIT
        transactions = await self._store.list_transactions(
            user.id, start, end, query.kind, query.currency, category, limit
        )
        return TransactionsAnswer(date_range, transactions, query.kind, query.currency, category)

    async def _find_category(
        self, user: User, name: str, query: ParsedQuery
    ) -> str | UnknownCategory:
        """El nombre exacto de la categoría pedida; sin coincidencia no se adivina."""
        kind = "expense" if query.tool == "spending_by_category" else query.kind
        candidates = [
            c for c in await self._categories.categories(user.id) if kind is None or c.kind == kind
        ]
        wanted = name.strip().casefold()
        for category in candidates:
            if category.name.casefold() == wanted:
                return category.name
        return UnknownCategory(name, sorted({c.name for c in candidates}))

    async def _balances(self, user: User, in_usd: bool) -> BalancesAnswer:
        rows = await self._store.account_balances(user.id)
        if not in_usd:
            return BalancesAnswer(rows, False, None, [], [])
        total = Decimal(0)
        used: dict[Currency, CurrentRate] = {}
        missing: list[Currency] = []
        for row in rows:
            if row.balance == 0:
                continue
            if row.currency == "USD":
                total += row.balance
                continue
            if row.currency not in used and row.currency not in missing:
                try:
                    used[row.currency] = await self._rates.for_user(user, row.currency)
                except RateUnavailable:
                    missing.append(row.currency)
            if row.currency in used:
                total += row.balance * used[row.currency].rate.usd_per_unit
        return BalancesAnswer(rows, True, total.quantize(USD_SCALE), list(used.values()), missing)
