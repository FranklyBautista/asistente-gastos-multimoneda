"""Caso de uso: registrar un cambio entre monedas y compararlo con la tasa de referencia.

La referencia se arma con las tasas guardadas (Fase 3): para el bolívar, la fuente que eligió
el usuario. Si una tasa no existe todavía, el cambio se guarda igual, sin referencia.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal, Protocol
from uuid import UUID

from gastos.domain.account import Account, pick_account
from gastos.domain.currency import CURRENCY_NAMES, Currency
from gastos.domain.errors import AccountNotFound, RateUnavailable
from gastos.domain.exchange import (
    ExchangeDraft,
    NewExchange,
    SavedExchange,
    complete_amounts,
    difference_pct,
    reference_rate,
)
from gastos.domain.user import User
from gastos.services.outcomes import Ask, NotATransaction
from gastos.services.rates import CurrentRate


class ExchangeStore(Protocol):
    """Lo implementa db.ExchangeRepository."""

    async def insert(self, user_id: UUID, item: NewExchange) -> SavedExchange: ...
    async def undo(self, user_id: UUID, exchange_id: UUID) -> int: ...


class AccountSource(Protocol):
    """Lo implementa db.TransactionRepository."""

    async def accounts(self, user_id: UUID) -> list[Account]: ...


class UserRates(Protocol):
    """Lo implementa services.RateService."""

    async def for_user(
        self, user: User, currency: Literal["VES", "COP", "USDT"]
    ) -> CurrentRate: ...


@dataclass(frozen=True, slots=True)
class ExchangeSaved:
    exchange: SavedExchange
    difference_pct: Decimal | None  # positivo: recibiste más que con la tasa de referencia
    reference_rates: list[CurrentRate]  # las tasas guardadas con que se armó la referencia


ExchangeOutcome = ExchangeSaved | Ask | NotATransaction


class ExchangeService:
    def __init__(self, store: ExchangeStore, accounts: AccountSource, rates: UserRates) -> None:
        self._store = store
        self._accounts = accounts
        self._rates = rates

    async def register(self, user: User, draft: ExchangeDraft, raw_text: str) -> ExchangeOutcome:
        source, target = draft.from_currency, draft.to_currency
        if source is None:
            if target is None:
                return Ask("¿De qué moneda a qué moneda fue el cambio?")
            return Ask(f"¿Qué moneda entregaste para recibir los {CURRENCY_NAMES[target]}?")
        if target is None:
            return Ask(f"¿Qué moneda recibiste por los {CURRENCY_NAMES[source]}?")
        if source == target:
            return NotATransaction("transfer")

        source_rate, target_rate = await self._rate(user, source), await self._rate(user, target)
        reference = _reference(source, source_rate, target, target_rate)
        amounts = complete_amounts(draft.from_amount, draft.to_amount, draft.quoted_rate, reference)
        if amounts is None:
            return Ask(_missing_question(draft, source, target))

        accounts = await self._accounts.accounts(user.id)
        from_account = pick_account(accounts, source, draft.from_account_hint)
        to_account = pick_account(accounts, target, draft.to_account_hint)
        if from_account is None:
            raise AccountNotFound(source)
        if to_account is None:
            raise AccountNotFound(target)

        saved = await self._store.insert(
            user.id,
            NewExchange(
                from_account=from_account,
                to_account=to_account,
                amounts=amounts,
                reference_rate=reference,
                occurred_at=draft.occurred_at,
                raw_text=raw_text,
            ),
        )
        diff = None if reference is None else difference_pct(amounts.effective_rate, reference)
        used = [r for r in (source_rate, target_rate) if r is not None]
        return ExchangeSaved(saved, diff, used)

    async def undo(self, user: User, exchange_id: UUID) -> int:
        return await self._store.undo(user.id, exchange_id)

    async def _rate(self, user: User, currency: Currency) -> CurrentRate | None:
        """La tasa guardada de la moneda; None para USD (es el pivote) o si no hay ninguna."""
        if currency == "USD":
            return None
        try:
            return await self._rates.for_user(user, currency)
        except RateUnavailable:
            return None


def _reference(
    source: Currency,
    source_rate: CurrentRate | None,
    target: Currency,
    target_rate: CurrentRate | None,
) -> Decimal | None:
    """Tasa de referencia "destino por 1 de origen"; None si falta la tasa de alguna moneda."""
    values: list[Decimal] = []
    for currency, current in ((source, source_rate), (target, target_rate)):
        if currency == "USD":
            values.append(Decimal(1))
        elif current is None:
            return None
        else:
            values.append(current.rate.usd_per_unit)
    return reference_rate(values[0], values[1])


def _missing_question(draft: ExchangeDraft, source: Currency, target: Currency) -> str:
    """Una sola pregunta corta por lo que falta (se conoce como mucho uno de los tres datos)."""
    given, received = CURRENCY_NAMES[source], CURRENCY_NAMES[target]
    if draft.from_amount is not None:
        return f"¿A qué tasa cambiaste o cuántos {received} recibiste?"
    if draft.to_amount is not None:
        return f"¿Cuántos {given} entregaste o a qué tasa fue?"
    if draft.quoted_rate is not None:
        return f"¿Cuántos {given} cambiaste?"
    return f"¿Cuántos {given} cambiaste y a qué tasa?"
