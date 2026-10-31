"""Dobles de prueba compartidos (sin red ni base de datos)."""

from collections.abc import Sequence
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel

from gastos.domain.account import Account, Category
from gastos.domain.conversion import Rate
from gastos.domain.currency import Currency, QuotedCurrency, RateSource, VesRateSource
from gastos.domain.transaction import NewTransaction, SavedTransaction
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
    """Implementa services.transactions.TextExtractor con una respuesta fija."""

    def __init__(self, result: Extraction) -> None:
        self.result = result
        self.calls: list[tuple[str, Categories, datetime]] = []

    async def extract(self, text: str, categories: Categories, now_local: datetime) -> Extraction:
        self.calls.append((text, categories, now_local))
        return self.result


class FakeLLM:
    """Implementa llm.LLMClient: devuelve las respuestas en orden (dict → se valida)."""

    def __init__(self, *responses: dict[str, Any] | Exception) -> None:
        self._responses = list(responses)
        self.calls: list[tuple[str, str]] = []

    async def structured[T: BaseModel](self, *, system: str, prompt: str, schema: type[T]) -> T:
        self.calls.append((system, prompt))
        return schema.model_validate(_or_raise(self._responses.pop(0)))
