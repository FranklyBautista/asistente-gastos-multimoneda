"""Caso de uso: registrar gastos e ingresos escritos en lenguaje natural.

Flujo: texto → `Extraction` del LLM → borradores. Si alguno tiene la moneda dudosa, se guarda
como pendiente y se pregunta con botones; si no, se resuelven cuenta, categoría y snapshot de
tasa y se guardan todos juntos.

Los pendientes viven en memoria: si el bot se reinicia antes de que el usuario elija la
moneda, el botón avisa que expiró y basta con reenviar el mensaje.
"""

import secrets
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Final, Literal, Protocol
from uuid import UUID
from zoneinfo import ZoneInfo

from gastos.domain.account import Account, Category, pick_account
from gastos.domain.conversion import Rate, to_usd
from gastos.domain.currency import Currency
from gastos.domain.errors import AccountNotFound
from gastos.domain.transaction import (
    FALLBACK_CATEGORY,
    NewTransaction,
    SavedTransaction,
    TransactionDraft,
)
from gastos.domain.user import User
from gastos.extraction.parser import Categories, to_drafts
from gastos.extraction.schema import Extraction
from gastos.services.rates import CurrentRate

PENDING_TTL: Final = timedelta(minutes=30)
MAX_PENDING: Final = 500  # tope de memoria; se descartan los más viejos


class TransactionStore(Protocol):
    """Lo implementa db.TransactionRepository."""

    async def accounts(self, user_id: UUID) -> list[Account]: ...
    async def categories(self, user_id: UUID) -> list[Category]: ...
    async def insert_many(
        self, user_id: UUID, items: Sequence[NewTransaction]
    ) -> list[SavedTransaction]: ...
    async def undo_batch(self, user_id: UUID, transaction_id: UUID) -> int: ...


class TextExtractor(Protocol):
    """Lo implementa extraction.Extractor."""

    async def extract(
        self, text: str, categories: Categories, now_local: datetime
    ) -> Extraction: ...


class UserRates(Protocol):
    """Lo implementa services.RateService."""

    async def for_user(
        self, user: User, currency: Literal["VES", "COP", "USDT"]
    ) -> CurrentRate: ...


# ---- Resultados que el chat convierte en mensajes ----


@dataclass(frozen=True, slots=True)
class Saved:
    transactions: list[SavedTransaction]
    stale_rates: list[Rate]  # tasas usadas que llevan tiempo sin actualizarse


@dataclass(frozen=True, slots=True)
class NeedsCurrency:
    token: str
    drafts: list[TransactionDraft]  # todos los del mensaje; los dudosos con `needs_currency`


@dataclass(frozen=True, slots=True)
class Ask:
    question: str


@dataclass(frozen=True, slots=True)
class NotATransaction:
    intent: Literal["log_exchange", "query", "correction", "other"]


Outcome = Saved | NeedsCurrency | Ask | NotATransaction


@dataclass(slots=True)
class _Pending:
    user_id: UUID
    drafts: list[TransactionDraft]
    raw_text: str
    confidence: float
    expires_at: datetime


@dataclass(slots=True)
class PendingStore:
    """Mensajes esperando que el usuario elija la moneda, por token de un solo uso."""

    clock: Callable[[], datetime] = lambda: datetime.now(UTC)
    _items: dict[str, _Pending] = field(default_factory=dict[str, _Pending])

    def put(self, item: _Pending) -> str:
        now = self.clock()
        self._items = {k: v for k, v in self._items.items() if v.expires_at > now}
        while len(self._items) >= MAX_PENDING:
            del self._items[next(iter(self._items))]
        token = secrets.token_urlsafe(6)
        self._items[token] = item
        return token

    def take(self, token: str, user_id: UUID) -> _Pending | None:
        item = self._items.get(token)
        if item is None or item.user_id != user_id:
            return None
        del self._items[token]
        return item if item.expires_at > self.clock() else None


class TransactionService:
    def __init__(
        self,
        store: TransactionStore,
        extractor: TextExtractor,
        rates: UserRates,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._store = store
        self._extractor = extractor
        self._rates = rates
        self._clock = clock
        self._pending = PendingStore(clock)

    async def register_text(self, user: User, text: str) -> Outcome:
        now_local = self._clock().astimezone(ZoneInfo(user.timezone))
        categories = await self._store.categories(user.id)
        names = _category_names(categories)
        extraction = await self._extractor.extract(text, names, now_local)

        if extraction.intent != "log_transactions":
            return NotATransaction(extraction.intent)
        if extraction.clarification and extraction.clarification.field != "currency":
            return Ask(extraction.clarification.question)
        drafts = to_drafts(extraction.transactions, names, now_local)
        if not drafts:
            return Ask("No encontré ningún monto. ¿Cuánto fue y en qué?")
        if any(d.needs_currency for d in drafts):
            pending = _Pending(
                user.id, drafts, text, extraction.confidence, self._clock() + PENDING_TTL
            )
            return NeedsCurrency(self._pending.put(pending), drafts)
        return await self._save(user, drafts, text, extraction.confidence, categories)

    async def choose_currency(self, user: User, token: str, currency: Currency) -> Saved | None:
        """Aplica la moneda elegida a los movimientos dudosos y guarda; None si expiró."""
        pending = self._pending.take(token, user.id)
        if pending is None:
            return None
        drafts = [d.with_currency(currency) if d.needs_currency else d for d in pending.drafts]
        categories = await self._store.categories(user.id)
        return await self._save(user, drafts, pending.raw_text, pending.confidence, categories)

    async def undo(self, user: User, transaction_id: UUID) -> int:
        return await self._store.undo_batch(user.id, transaction_id)

    async def _save(
        self,
        user: User,
        drafts: list[TransactionDraft],
        raw_text: str,
        confidence: float,
        categories: list[Category],
    ) -> Saved:
        accounts = await self._store.accounts(user.id)
        rates: dict[Currency, CurrentRate | None] = {}
        items: list[NewTransaction] = []
        for draft in drafts:
            currency = draft.currency
            if currency is None:  # el flujo de arriba lo impide; si pasa, es un bug
                raise ValueError("borrador sin moneda")
            account = pick_account(accounts, currency, draft.account_hint)
            if account is None:
                raise AccountNotFound(currency)
            if currency not in rates:
                rates[currency] = (
                    None if currency == "USD" else await self._rates.for_user(user, currency)
                )
            current = rates[currency]
            items.append(
                NewTransaction(
                    account=account,
                    kind=draft.kind,
                    amount=draft.amount,
                    category=_category_for(categories, draft),
                    description=draft.description,
                    snapshot=to_usd(draft.amount, currency, current.rate if current else None),
                    occurred_at=draft.occurred_at,
                    raw_text=raw_text,
                    parse_confidence=min(confidence, draft.currency_confidence),
                )
            )
        saved = await self._store.insert_many(user.id, items)
        stale = [c.rate for c in rates.values() if c is not None and c.stale]
        return Saved(saved, stale)


def _category_names(categories: Sequence[Category]) -> Categories:
    return Categories(
        expense=[c.name for c in categories if c.kind == "expense"],
        income=[c.name for c in categories if c.kind == "income"],
    )


def _category_for(categories: Sequence[Category], draft: TransactionDraft) -> Category:
    wanted = draft.category or FALLBACK_CATEGORY[draft.kind]
    for name in (wanted, FALLBACK_CATEGORY[draft.kind]):
        for category in categories:
            if category.kind == draft.kind and category.name == name:
                return category
    raise LookupError(f"no existe la categoría de respaldo {FALLBACK_CATEGORY[draft.kind]!r}")
