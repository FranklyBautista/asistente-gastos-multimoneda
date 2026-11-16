"""Casos de uso de deudas (Fase 11, ADR 0016): anotarlas, pagarlas y listarlas.

Pagar una deuda puede pedir hasta dos elecciones con botones: cuál deuda (si hay varias de esa
persona) y de qué cuenta salió o a cuál entró el dinero (o «Sin movimiento»). Mientras tanto,
el pago vive en memoria con un token de un solo uso, como la moneda dudosa de la Fase 4.
"""

import secrets
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Final, Literal, Protocol
from uuid import UUID

from gastos.domain.account import Account, Category, pick_account
from gastos.domain.conversion import Rate, to_usd
from gastos.domain.currency import Currency
from gastos.domain.debt import (
    PAYMENT_CATEGORY,
    PAYMENT_KIND,
    Debt,
    DebtDirection,
    DebtDraft,
    NewDebt,
    PaymentDraft,
    matching_debts,
    same_person,
)
from gastos.domain.money import format_money
from gastos.domain.transaction import NewTransaction, SavedTransaction
from gastos.domain.user import User
from gastos.services.outcomes import Ask
from gastos.services.rates import CurrentRate

PENDING_TTL: Final = timedelta(minutes=30)
MAX_PENDING: Final = 500


class DebtStore(Protocol):
    """Lo implementa db.DebtRepository."""

    async def insert(self, user_id: UUID, item: NewDebt) -> Debt: ...
    async def list(
        self,
        user_id: UUID,
        *,
        direction: DebtDirection | None = None,
        include_settled: bool = False,
    ) -> list[Debt]: ...
    async def get(self, user_id: UUID, debt_id: UUID) -> Debt | None: ...
    async def pay(
        self,
        user_id: UUID,
        debt: Debt,
        amount: Decimal,
        movement: NewTransaction | None,
        raw_text: str,
    ) -> tuple[UUID, SavedTransaction | None, Debt]: ...
    async def cancel(self, user_id: UUID, debt_id: UUID) -> int: ...
    async def undo_payment(self, user_id: UUID, payment_id: UUID) -> int: ...


class AccountSource(Protocol):
    """Lo implementa db.TransactionRepository."""

    async def accounts(self, user_id: UUID) -> list[Account]: ...
    async def categories(self, user_id: UUID) -> list[Category]: ...


class UserRates(Protocol):
    """Lo implementa services.RateService."""

    async def for_user(
        self, user: User, currency: Literal["VES", "COP", "USDT"]
    ) -> CurrentRate: ...


# ---- Resultados que el chat convierte en mensajes ----


@dataclass(frozen=True, slots=True)
class DebtSaved:
    debt: Debt
    stale_rate: Rate | None = None


@dataclass(frozen=True, slots=True)
class NeedsDebtCurrency:
    token: str
    draft: DebtDraft


@dataclass(frozen=True, slots=True)
class NoMatchingDebt:
    """No hay una deuda pendiente que cuadre; se muestran las abiertas de esa dirección."""

    payment: PaymentDraft
    open_debts: list[Debt]


@dataclass(frozen=True, slots=True)
class ChooseDebt:
    token: str
    payment: PaymentDraft
    candidates: list[Debt]


@dataclass(frozen=True, slots=True)
class ChooseAccount:
    token: str
    debt: Debt
    amount: Decimal
    accounts: list[Account]


@dataclass(frozen=True, slots=True)
class PaymentSaved:
    payment_id: UUID
    amount: Decimal
    debt: Debt  # cómo quedó después del pago
    movement: SavedTransaction | None  # None = sin movimiento de dinero


@dataclass(frozen=True, slots=True)
class DebtList:
    debts: list[Debt]
    direction: DebtDirection | None
    counterparty: str | None = None
    include_settled: bool = False


DebtOutcome = (
    DebtSaved | NeedsDebtCurrency | NoMatchingDebt | ChooseDebt | ChooseAccount | PaymentSaved | Ask
)


# ---- Pendientes en memoria ----


@dataclass(slots=True)
class _PendingDebt:
    user_id: UUID
    draft: DebtDraft
    raw_text: str
    expires_at: datetime


@dataclass(slots=True)
class _PendingPayment:
    user_id: UUID
    payment: PaymentDraft
    raw_text: str
    expires_at: datetime
    candidates: list[Debt] = field(default_factory=list[Debt])
    debt: Debt | None = None
    amount: Decimal | None = None
    accounts: list[Account] = field(default_factory=list[Account])


class _Tokens[T: (_PendingDebt, _PendingPayment)]:
    """Pendientes por token de un solo uso; se descartan al vencer o al pasar MAX_PENDING."""

    def __init__(self, clock: Callable[[], datetime]) -> None:
        self._clock = clock
        self._items: dict[str, T] = {}

    def put(self, item: T) -> str:
        now = self._clock()
        self._items = {k: v for k, v in self._items.items() if v.expires_at > now}
        while len(self._items) >= MAX_PENDING:
            del self._items[next(iter(self._items))]
        token = secrets.token_urlsafe(6)
        self._items[token] = item
        return token

    def peek(self, token: str, user_id: UUID) -> T | None:
        item = self._items.get(token)
        if item is None or item.user_id != user_id or item.expires_at <= self._clock():
            return None
        return item

    def drop(self, token: str) -> None:
        self._items.pop(token, None)


class DebtService:
    def __init__(
        self,
        store: DebtStore,
        accounts: AccountSource,
        rates: UserRates,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._store = store
        self._accounts = accounts
        self._rates = rates
        self._clock = clock
        self._debts = _Tokens[_PendingDebt](clock)
        self._payments = _Tokens[_PendingPayment](clock)

    # ---- Anotar ----

    async def register(self, user: User, draft: DebtDraft, raw_text: str) -> DebtOutcome:
        if draft.needs_currency:
            item = _PendingDebt(user.id, draft, raw_text, self._clock() + PENDING_TTL)
            return NeedsDebtCurrency(self._debts.put(item), draft)
        return await self._save_debt(user, draft, raw_text)

    async def choose_currency(self, user: User, token: str, currency: Currency) -> DebtSaved | None:
        pending = self._debts.peek(token, user.id)
        if pending is None:
            return None
        self._debts.drop(token)
        return await self._save_debt(user, pending.draft.with_currency(currency), pending.raw_text)

    async def _save_debt(self, user: User, draft: DebtDraft, raw_text: str) -> DebtSaved:
        currency = draft.currency
        if currency is None:  # el flujo de arriba lo impide; si pasa, es un bug
            raise ValueError("deuda sin moneda")
        current = None if currency == "USD" else await self._rates.for_user(user, currency)
        category = None
        if draft.category:
            categories = await self._accounts.categories(user.id)
            category = next(
                (c for c in categories if c.kind == "expense" and c.name == draft.category), None
            )
        debt = await self._store.insert(
            user.id,
            NewDebt(
                direction=draft.direction,
                counterparty=draft.counterparty,
                currency=currency,
                amount=draft.amount,
                category=category,
                description=draft.description,
                snapshot=to_usd(draft.amount, currency, current.rate if current else None),
                raw_text=raw_text,
            ),
        )
        return DebtSaved(debt, current.rate if current and current.stale else None)

    async def undo_debt(self, user: User, debt_id: UUID) -> int:
        return await self._store.cancel(user.id, debt_id)

    # ---- Pagar ----

    async def settle(self, user: User, payment: PaymentDraft, raw_text: str) -> DebtOutcome:
        open_debts = await self._store.list(user.id, direction=payment.direction)
        matches = matching_debts(open_debts, payment)
        if not matches:
            return NoMatchingDebt(payment, open_debts)
        if payment.amount is not None:
            fits = [d for d in matches if d.remaining >= payment.amount]
            if not fits:
                return Ask(_exceeds_question(payment, matches))
            matches = fits
        pending = _PendingPayment(user.id, payment, raw_text, self._clock() + PENDING_TTL)
        if len(matches) > 1:
            pending.candidates = matches
            return ChooseDebt(self._payments.put(pending), payment, matches)
        return await self._with_debt(user, pending, matches[0])

    async def choose_debt(self, user: User, token: str, index: int) -> DebtOutcome | None:
        pending = self._payments.peek(token, user.id)
        if pending is None or not 0 <= index < len(pending.candidates):
            return None
        self._payments.drop(token)
        return await self._with_debt(user, pending, pending.candidates[index])

    async def choose_account(
        self, user: User, token: str, index: int | None
    ) -> PaymentSaved | None:
        """`index` None = «Sin movimiento»: el pago se anota sin tocar ninguna cuenta."""
        pending = self._payments.peek(token, user.id)
        if pending is None or pending.debt is None or pending.amount is None:
            return None
        if index is not None and not 0 <= index < len(pending.accounts):
            return None
        self._payments.drop(token)
        account = None if index is None else pending.accounts[index]
        return await self._pay(user, pending.debt, pending.amount, account, pending.raw_text)

    async def _with_debt(self, user: User, pending: _PendingPayment, debt: Debt) -> DebtOutcome:
        """Ya se sabe qué deuda paga: decide el monto y pregunta (o deduce) la cuenta."""
        amount = debt.remaining if pending.payment.amount is None else pending.payment.amount
        if amount > debt.remaining:
            return Ask(_exceeds_question(pending.payment, [debt]))
        accounts = [
            a for a in await self._accounts.accounts(user.id) if a.currency == debt.currency
        ]
        hinted = _hinted_account(accounts, debt.currency, pending.payment.account_hint)
        if hinted is not None:
            return await self._pay(user, debt, amount, hinted, pending.raw_text)
        pending.debt, pending.amount, pending.accounts = debt, amount, accounts
        pending.expires_at = self._clock() + PENDING_TTL
        return ChooseAccount(self._payments.put(pending), debt, amount, accounts)

    async def _pay(
        self,
        user: User,
        debt: Debt,
        amount: Decimal,
        account: Account | None,
        raw_text: str,
    ) -> PaymentSaved:
        movement = None
        if account is not None:
            movement = await self._movement(user, debt, amount, account, raw_text)
        payment_id, saved, after = await self._store.pay(user.id, debt, amount, movement, raw_text)
        return PaymentSaved(payment_id, amount, after, saved)

    async def _movement(
        self, user: User, debt: Debt, amount: Decimal, account: Account, raw_text: str
    ) -> NewTransaction:
        kind = PAYMENT_KIND[debt.direction]
        name = PAYMENT_CATEGORY[debt.direction]
        categories = await self._accounts.categories(user.id)
        category = next((c for c in categories if c.kind == kind and c.name == name), None)
        if category is None:
            raise LookupError(f"no existe la categoría {name!r} (migración debt_categories)")
        current = (
            None if debt.currency == "USD" else await self._rates.for_user(user, debt.currency)
        )
        return NewTransaction(
            account=account,
            kind=kind,
            amount=amount,
            category=category,
            description=f"deuda con {debt.counterparty}"[:200],
            snapshot=to_usd(amount, debt.currency, current.rate if current else None),
            occurred_at=None,
            raw_text=raw_text,
            parse_confidence=1.0,
        )

    async def undo_payment(self, user: User, payment_id: UUID) -> int:
        return await self._store.undo_payment(user.id, payment_id)

    # ---- Consultar ----

    async def list(
        self,
        user: User,
        *,
        direction: DebtDirection | None = None,
        counterparty: str | None = None,
        include_settled: bool = False,
    ) -> DebtList:
        debts = await self._store.list(
            user.id, direction=direction, include_settled=include_settled
        )
        if counterparty:
            debts = [d for d in debts if same_person(counterparty, d)]
        return DebtList(debts, direction, counterparty, include_settled)


def _hinted_account(
    accounts: Sequence[Account], currency: Currency, hint: str | None
) -> Account | None:
    """La cuenta solo se deduce si la pista coincide de verdad con una (no la primera)."""
    if not hint:
        return None
    found = pick_account(list(accounts), currency, hint)
    if found is None:
        return None
    needle, name = hint.strip().casefold(), found.name.casefold()
    return found if needle in name or name in needle else None


def _exceeds_question(payment: PaymentDraft, debts: Sequence[Debt]) -> str:
    """El pago es mayor que lo pendiente: se dice cuánto falta y se pregunta el monto."""
    if len(debts) == 1:
        d = debts[0]
        pending = format_money(d.remaining, d.currency)
        return (
            f"Con {d.counterparty} tienes pendiente {pending}, menos de lo que dices. "
            "¿Cuánto fue el pago?"
        )
    pending = ", ".join(format_money(d.remaining, d.currency) for d in debts)
    return (
        f"Con {debts[0].counterparty} tienes pendiente {pending}, y ninguna llega a ese monto. "
        "¿Cuánto fue el pago?"
    )
