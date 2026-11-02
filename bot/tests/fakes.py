"""Dobles de prueba compartidos (sin red ni base de datos)."""

from collections.abc import Sequence
from dataclasses import replace
from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel

from gastos.domain.account import Account, Category
from gastos.domain.conversion import Rate
from gastos.domain.currency import Currency, QuotedCurrency, RateSource, VesRateSource
from gastos.domain.exchange import NewExchange, SavedExchange
from gastos.domain.reports import AccountBalance, CategoryTotal, CurrencyTotal, TransactionRow
from gastos.domain.transaction import NewTransaction, SavedTransaction, TransactionKind
from gastos.domain.user import User
from gastos.extraction.parser import Categories
from gastos.extraction.schema import Extraction


def make_user(telegram_id: int = 111, *, onboarded: bool = False) -> User:
    return User(
        id=uuid4(),
        telegram_id=telegram_id,
        display_name="Ana",
        timezone="America/Caracas",
        default_currency="USD",
        ves_rate_source="parallel",
        onboarded_at=datetime(2026, 10, 15, tzinfo=UTC) if onboarded else None,
    )


class FakeUserStore:
    """Implementa services.users.UserStore en memoria."""

    def __init__(self) -> None:
        self.by_id: dict[UUID, User] = {}
        self.created = 0

    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        return next((u for u in self.by_id.values() if u.telegram_id == telegram_id), None)

    async def create(self, telegram_id: int, display_name: str | None) -> User:
        self.created += 1
        user = replace(make_user(telegram_id), display_name=display_name)
        self.by_id[user.id] = user
        return user

    async def set_default_currency(self, user_id: UUID, currency: Currency) -> User:
        return self._save(replace(self.by_id[user_id], default_currency=currency))

    async def set_ves_rate_source(self, user_id: UUID, source: VesRateSource) -> User:
        return self._save(replace(self.by_id[user_id], ves_rate_source=source))

    async def complete_onboarding(self, user_id: UUID, timezone: str) -> User:
        current = self.by_id[user_id]
        onboarded_at = current.onboarded_at or datetime.now(UTC)
        return self._save(replace(current, timezone=timezone, onboarded_at=onboarded_at))

    def _save(self, user: User) -> User:
        self.by_id[user.id] = user
        return user


class FakeRateStore:
    """Implementa services.rates.RateStore en memoria."""

    def __init__(self, *rates: Rate) -> None:
        self.rows: list[Rate] = list(rates)

    async def save(self, rates: Sequence[Rate]) -> None:
        self.rows.extend(rates)

    async def latest(self, currency: QuotedCurrency, source: RateSource) -> Rate | None:
        matching = [r for r in self.rows if (r.currency, r.source) == (currency, source)]
        return max(matching, key=lambda r: r.fetched_at, default=None)

    async def at(
        self, currency: QuotedCurrency, source: RateSource, moment: datetime
    ) -> Rate | None:
        matching = [r for r in self.rows if (r.currency, r.source) == (currency, source)]
        before = [r for r in matching if r.fetched_at <= moment]
        if before:
            return max(before, key=lambda r: r.fetched_at)
        return min(matching, key=lambda r: r.fetched_at, default=None)


class FakeRateSources:
    """Implementa services.rates.RateSources; una fuente con una excepción simula una caída."""

    def __init__(
        self,
        *,
        dolarapi: list[Rate] | Exception,
        p2p: Rate | Exception,
        cop: Rate | Exception,
        usdt: Rate | Exception,
    ) -> None:
        self._dolarapi = dolarapi
        self._p2p = p2p
        self._cop = cop
        self._usdt = usdt
        self.p2p_crossed_with: Rate | None = None

    async def ves_dolarapi(self) -> list[Rate]:
        return _or_raise(self._dolarapi)

    async def ves_p2p(self, usdt_rate: Rate) -> Rate:
        self.p2p_crossed_with = usdt_rate
        return _or_raise(self._p2p)

    async def cop(self) -> Rate:
        return _or_raise(self._cop)

    async def usdt(self) -> Rate:
        return _or_raise(self._usdt)


def _or_raise[T](result: T | Exception) -> T:
    if isinstance(result, Exception):
        raise result
    return result


# ---- Registro de movimientos (Fase 4) ----


def make_accounts() -> list[Account]:
    """Las 4 cuentas que crea el trigger, más una de banco en Bs."""
    return [
        Account(uuid4(), "banesco", "VES", "bank"),
        Account(uuid4(), "efectivo Bs", "VES", "cash"),
        Account(uuid4(), "efectivo COP", "COP", "cash"),
        Account(uuid4(), "efectivo USD", "USD", "cash"),
        Account(uuid4(), "wallet USDT", "USDT", "wallet"),
    ]


def make_categories() -> list[Category]:
    expense = ["comida", "otros", "ocio", "salud", "servicios", "transporte"]
    income = ["otros ingresos", "salario"]
    return [Category(uuid4(), n, "expense") for n in expense] + [
        Category(uuid4(), n, "income") for n in income
    ]


class FakeTransactionStore:
    """Implementa services.transactions.TransactionStore en memoria."""

    def __init__(self) -> None:
        self.account_list = make_accounts()
        self.category_list = make_categories()
        self.batches: list[list[NewTransaction]] = []
        self.saved: dict[UUID, tuple[int, bool]] = {}  # id → (lote, borrado)

    async def accounts(self, user_id: UUID) -> list[Account]:
        return self.account_list

    async def categories(self, user_id: UUID) -> list[Category]:
        return self.category_list

    async def insert_many(
        self, user_id: UUID, items: Sequence[NewTransaction]
    ) -> list[SavedTransaction]:
        self.batches.append(list(items))
        saved: list[SavedTransaction] = []
        for item in items:
            tx_id = uuid4()
            self.saved[tx_id] = (len(self.batches) - 1, False)
            saved.append(
                SavedTransaction(
                    id=tx_id,
                    kind=item.kind,
                    amount=item.amount,
                    currency=item.currency,
                    category=item.category.name,
                    description=item.description,
                    account_name=item.account.name,
                    snapshot=item.snapshot,
                    occurred_at=item.occurred_at or datetime.now(UTC),
                )
            )
        return saved

    async def undo_batch(self, user_id: UUID, transaction_id: UUID) -> int:
        if transaction_id not in self.saved:
            return 0
        batch, _ = self.saved[transaction_id]
        ids = [k for k, (b, deleted) in self.saved.items() if b == batch and not deleted]
        for k in ids:
            self.saved[k] = (batch, True)
        return len(ids)


class FakeExtractor:
    """Implementa services.transactions.TextExtractor: devuelve las respuestas en orden.

    La última se repite, así que con una sola respuesta sirve para cualquier número de llamadas.
    """

    def __init__(self, *results: Extraction) -> None:
        self.results = list(results)
        self.calls: list[tuple[str, tuple[str, str] | None]] = []

    async def extract(
        self,
        text: str,
        categories: Categories,
        now_local: datetime,
        previous: tuple[str, str] | None = None,
    ) -> Extraction:
        self.calls.append((text, previous))
        return self.results.pop(0) if len(self.results) > 1 else self.results[0]


class FakeExchangeStore:
    """Implementa services.exchanges.ExchangeStore en memoria."""

    def __init__(self) -> None:
        self.saved: list[NewExchange] = []
        self.deleted: set[UUID] = set()
        self.ids: list[UUID] = []

    async def insert(self, user_id: UUID, item: NewExchange) -> SavedExchange:
        self.saved.append(item)
        exchange_id = uuid4()
        self.ids.append(exchange_id)
        return SavedExchange(
            id=exchange_id,
            from_currency=item.from_account.currency,
            to_currency=item.to_account.currency,
            amounts=item.amounts,
            reference_rate=item.reference_rate,
            from_account_name=item.from_account.name,
            to_account_name=item.to_account.name,
            occurred_at=item.occurred_at or datetime.now(UTC),
        )

    async def undo(self, user_id: UUID, exchange_id: UUID) -> int:
        if exchange_id not in self.ids or exchange_id in self.deleted:
            return 0
        self.deleted.add(exchange_id)
        return 1


class FakeLLM:
    """Implementa llm.LLMClient: devuelve las respuestas en orden (dict → se valida)."""

    def __init__(self, *responses: dict[str, Any] | Exception) -> None:
        self._responses = list(responses)
        self.calls: list[tuple[str, str]] = []

    async def structured[T: BaseModel](self, *, system: str, prompt: str, schema: type[T]) -> T:
        self.calls.append((system, prompt))
        return schema.model_validate(_or_raise(self._responses.pop(0)))


class FakeReportStore:
    """Implementa services.query_tools.ReportStore: respuestas fijas y registro de llamadas."""

    def __init__(
        self,
        *,
        spending: list[CategoryTotal] | None = None,
        totals: list[CurrencyTotal] | None = None,
        balances: list[AccountBalance] | None = None,
        transactions: list[TransactionRow] | None = None,
    ) -> None:
        self.spending = spending or []
        self.totals_rows = totals or []
        self.balances = balances or []
        self.transactions = transactions or []
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def spending_by_category(
        self, user_id: UUID, start: datetime, end: datetime, currency: Currency | None
    ) -> list[CategoryTotal]:
        self.calls.append(("spending", {"start": start, "end": end, "currency": currency}))
        return self.spending

    async def totals(
        self,
        user_id: UUID,
        kind: TransactionKind,
        start: datetime,
        end: datetime,
        currency: Currency | None,
        category: str | None,
    ) -> list[CurrencyTotal]:
        self.calls.append(
            (
                "totals",
                {
                    "kind": kind,
                    "start": start,
                    "end": end,
                    "currency": currency,
                    "category": category,
                },
            )
        )
        return self.totals_rows

    async def account_balances(self, user_id: UUID) -> list[AccountBalance]:
        self.calls.append(("balances", {}))
        return self.balances

    async def list_transactions(
        self,
        user_id: UUID,
        start: datetime,
        end: datetime,
        kind: TransactionKind | None,
        currency: Currency | None,
        category: str | None,
        limit: int,
    ) -> list[TransactionRow]:
        self.calls.append(
            (
                "list",
                {
                    "start": start,
                    "end": end,
                    "kind": kind,
                    "currency": currency,
                    "category": category,
                    "limit": limit,
                },
            )
        )
        return self.transactions


# ---- Resumen semanal (Fase 7) ----


class FakeSentSummaries:
    """Implementa services.weekly_summary.SentSummaries en memoria."""

    def __init__(self) -> None:
        self.claimed: set[tuple[UUID, date]] = set()
        self.released: list[tuple[UUID, date]] = []

    async def claim(self, user_id: UUID, week_start: date) -> bool:
        if (user_id, week_start) in self.claimed:
            return False
        self.claimed.add((user_id, week_start))
        return True

    async def release(self, user_id: UUID, week_start: date) -> None:
        self.claimed.discard((user_id, week_start))
        self.released.append((user_id, week_start))


class FakeRecipients:
    """Implementa services.weekly_summary.Recipients."""

    def __init__(self, *users: User) -> None:
        self.users = list(users)

    async def onboarded(self) -> list[User]:
        return [u for u in self.users if u.is_onboarded]
