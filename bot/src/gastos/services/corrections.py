"""Caso de uso: corregir el último movimiento y recordar la corrección.

"eso fue transporte", "eran 20 mil pesos" o `/corregir era un ingreso` modifican el último
mensaje anotado (si tenía varios movimientos, el que se nombre). Cada campo cambiado queda en
`corrections`, y las más recientes vuelven al prompt de extracción como ejemplos (ADR 0009).
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Final, Literal, Protocol
from uuid import UUID

from gastos.domain.account import Account, Category, pick_account
from gastos.domain.conversion import Rate, UsdSnapshot, to_usd
from gastos.domain.correction import (
    Change,
    CorrectedValues,
    CorrectionDraft,
    CorrectionExample,
    LastBatch,
    StoredTransaction,
    changes_between,
    pick_target,
    rescale_snapshot,
)
from gastos.domain.currency import Currency, QuotedCurrency
from gastos.domain.errors import AccountNotFound
from gastos.domain.transaction import FALLBACK_CATEGORY, SavedTransaction, TransactionKind
from gastos.domain.user import User
from gastos.services.outcomes import Ask
from gastos.services.rates import CurrentRate

# Cuántas correcciones van al prompt: suficientes para aprender, pocas para no inflarlo.
MAX_EXAMPLES: Final = 10
# Una corrección por mensaje solo toca lo de las últimas 24 h; lo más viejo se edita en la web.
MAX_AGE: Final = timedelta(hours=24)
WHAT_TO_FIX = "¿Qué corrijo? Por ejemplo: «eso fue transporte» o «eran 20 mil pesos»."


class CorrectionStore(Protocol):
    """Lo implementa db.CorrectionRepository."""

    async def last_batch(self, user_id: UUID) -> LastBatch: ...
    async def apply(
        self,
        user_id: UUID,
        transaction_id: UUID,
        values: CorrectedValues,
        changes: list[Change],
        raw_text: str,
    ) -> bool: ...
    async def recent_examples(self, user_id: UUID, limit: int) -> list[CorrectionExample]: ...


class AccountsAndCategories(Protocol):
    """Lo implementa db.TransactionRepository."""

    async def accounts(self, user_id: UUID) -> list[Account]: ...
    async def categories(self, user_id: UUID) -> list[Category]: ...


class CorrectionRates(Protocol):
    """Lo implementa services.RateService."""

    async def for_user(self, user: User, currency: QuotedCurrency) -> CurrentRate: ...
    async def for_user_at(
        self, user: User, currency: QuotedCurrency, moment: datetime
    ) -> Rate | None: ...


@dataclass(frozen=True, slots=True)
class Corrected:
    transaction: SavedTransaction  # cómo quedó
    changes: list[Change]


@dataclass(frozen=True, slots=True)
class NoChange:
    """Lo que pidió ya estaba así."""

    transaction: SavedTransaction


NothingReason = Literal["none", "undone", "exchange", "expired"]


@dataclass(frozen=True, slots=True)
class NothingToCorrect:
    """No hay nada que corregir por mensaje, y por qué.

    - `none`: nunca anotó nada.
    - `undone`: lo último se deshizo (antes o mientras se corregía).
    - `exchange`: lo último fue un cambio de moneda.
    - `expired`: lo último tiene más de `MAX_AGE`; para eso está la edición en la web.
    """

    reason: NothingReason = "none"


CorrectionOutcome = Corrected | NoChange | NothingToCorrect | Ask


def _saved(tx_id: UUID, values: CorrectedValues, target: StoredTransaction) -> SavedTransaction:
    return SavedTransaction(
        id=tx_id,
        kind=values.kind,
        amount=values.amount,
        currency=values.account.currency,
        category=values.category.name,
        description=target.description,
        account_name=values.account.name,
        snapshot=values.snapshot,
        occurred_at=target.occurred_at,
    )


def as_saved(tx: StoredTransaction) -> SavedTransaction:
    values = CorrectedValues(tx.kind, tx.amount, tx.account, tx.category, tx.snapshot)
    return _saved(tx.id, values, tx)


def _account_for(
    accounts: list[Account], target: StoredTransaction, currency: Currency, hint: str | None
) -> Account:
    if currency == target.currency:
        if not hint:
            return target.account
        # En la misma moneda solo se cambia de cuenta si la pista coincide con una.
        same = [a for a in accounts if a.currency == currency]
        found = pick_account(same, currency, hint)
        needle = hint.strip().casefold()
        if found and (needle in found.name.casefold() or found.name.casefold() in needle):
            return found
        return target.account
    found = pick_account(accounts, currency, hint)
    if found is None:
        raise AccountNotFound(currency)
    return found


class CorrectionService:
    def __init__(
        self,
        store: CorrectionStore,
        accounts: AccountsAndCategories,
        rates: CorrectionRates,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._store = store
        self._accounts = accounts
        self._rates = rates
        self._clock = clock

    async def _batch(self, user: User) -> tuple[StoredTransaction, ...] | NothingToCorrect:
        """Lo que una corrección puede tocar: el último mensaje anotado, si es reciente."""
        last = await self._store.last_batch(user.id)
        if last.kind != "transactions" or not last.transactions:
            return NothingToCorrect("none" if last.kind == "transactions" else last.kind)
        if last.at is not None and self._clock() - last.at > MAX_AGE:
            return NothingToCorrect("expired")
        return last.transactions

    async def last(self, user: User) -> list[SavedTransaction] | NothingToCorrect:
        """Los movimientos del último mensaje, para mostrar qué se corregiría."""
        batch = await self._batch(user)
        if isinstance(batch, NothingToCorrect):
            return batch
        return [as_saved(tx) for tx in batch]

    async def examples(self, user: User) -> list[CorrectionExample]:
        return await self._store.recent_examples(user.id, MAX_EXAMPLES)

    async def correct(self, user: User, draft: CorrectionDraft, raw_text: str) -> CorrectionOutcome:
        if draft.is_empty:
            return Ask(WHAT_TO_FIX)
        batch = await self._batch(user)
        if isinstance(batch, NothingToCorrect):
            return batch
        target = pick_target(batch, draft.target_hint)
        if target is None:
            names = ", ".join(tx.description for tx in batch)
            return Ask(
                f"Tu último mensaje anotó varios movimientos ({names}). ¿Cuál corrijo? "
                f"Por ejemplo: «{batch[0].description} era transporte»."
            )

        kind: TransactionKind = draft.kind or target.kind
        currency = draft.currency or target.currency
        amount = draft.amount or target.amount
        account = _account_for(
            await self._accounts.accounts(user.id), target, currency, draft.account_hint
        )
        category = await self._category_for(user, draft, target, kind)
        if isinstance(category, Ask):
            return category
        snapshot = await self._snapshot(user, target, currency, amount)

        values = CorrectedValues(kind, amount, account, category, snapshot)
        changes = changes_between(target, values)
        if not changes:
            return NoChange(as_saved(target))
        if not await self._store.apply(user.id, target.id, values, changes, raw_text):
            return NothingToCorrect("undone")
        return Corrected(_saved(target.id, values, target), changes)

    async def _category_for(
        self, user: User, draft: CorrectionDraft, target: StoredTransaction, kind: TransactionKind
    ) -> Category | Ask:
        categories = [c for c in await self._accounts.categories(user.id) if c.kind == kind]
        if draft.category:
            wanted = draft.category.strip().casefold()
            for category in categories:
                if category.name.casefold() == wanted:
                    return category
            names = ", ".join(sorted(c.name for c in categories))
            return Ask(f"No tengo la categoría «{draft.category}». Las que hay: {names}.")
        if target.category.kind == kind:
            return target.category
        # Cambió de gasto a ingreso (o al revés): la categoría vieja ya no aplica.
        fallback = FALLBACK_CATEGORY[kind]
        return next(c for c in categories if c.name == fallback)

    async def _snapshot(
        self, user: User, target: StoredTransaction, currency: Currency, amount: Decimal
    ) -> UsdSnapshot:
        """Otra moneda: la tasa de cuando se anotó. Misma moneda: la misma tasa, otro monto.

        La web aplica la misma regla en la función SQL `edit_transaction` (ADR 0014).
        """
        if currency == target.currency:
            return rescale_snapshot(amount, target.snapshot)
        if currency == "USD":
            return to_usd(amount, "USD", None)
        rate = await self._rates.for_user_at(user, currency, target.created_at)
        if rate is None:
            rate = (await self._rates.for_user(user, currency)).rate
        return to_usd(amount, currency, rate)
