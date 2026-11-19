"""Caso de uso: registrar gastos, ingresos y cambios de moneda escritos en lenguaje natural.

Flujo: texto → `Extraction` del LLM → borradores. Si alguno tiene la moneda dudosa, se guarda
como pendiente y se pregunta con botones; si no, se resuelven cuenta, categoría y snapshot de
tasa y se guardan todos juntos.

Los pendientes viven en memoria: si el bot se reinicia antes de que el usuario elija la
moneda, el botón avisa que expiró y basta con reenviar el mensaje.
"""

import secrets
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from typing import Final, Literal, Protocol
from uuid import UUID
from zoneinfo import ZoneInfo

from gastos.domain.account import Account, Category, pick_account
from gastos.domain.conversion import Rate, to_usd
from gastos.domain.correction import CorrectionExample
from gastos.domain.currency import Currency
from gastos.domain.debt import DEBT_CATEGORIES
from gastos.domain.errors import AccountNotFound
from gastos.domain.transaction import (
    FALLBACK_CATEGORY,
    NewTransaction,
    SavedTransaction,
    TransactionDraft,
)
from gastos.domain.user import User
from gastos.extraction.parser import (
    Categories,
    to_budget_draft,
    to_correction_draft,
    to_debt_draft,
    to_drafts,
    to_exchange_draft,
    to_payment_draft,
)
from gastos.extraction.schema import Extraction
from gastos.services.budgets import BudgetOutcome, BudgetService, BudgetStatus
from gastos.services.context import ContextLine
from gastos.services.corrections import (
    WHAT_TO_FIX,
    CorrectionOutcome,
    CorrectionService,
    NothingToCorrect,
)
from gastos.services.debts import DebtList, DebtOutcome, DebtService
from gastos.services.exchanges import ExchangeSaved, ExchangeService
from gastos.services.outcomes import Ask, NotATransaction
from gastos.services.query_tools import QueryAnswer, QueryService, RunwayAnswer
from gastos.services.rates import CurrentRate

PENDING_TTL: Final = timedelta(minutes=30)
# Tiempo en que una respuesta suelta todavía se toma como respuesta a la pregunta del bot.
FOLLOWUP_TTL: Final = timedelta(minutes=10)
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
        self,
        text: str,
        categories: Categories,
        now_local: datetime,
        previous: tuple[str, str] | None = None,
        corrections: Sequence[CorrectionExample] = (),
    ) -> Extraction: ...


class ContextSource(Protocol):
    """Lo implementa services.ContextService (Fase 12)."""

    async def lines(self, user: User, saved: Sequence[SavedTransaction]) -> list[ContextLine]: ...


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
    # Tasas del Bs de otra fuente porque la del usuario no tenía una fresca.
    replaced_rates: list[CurrentRate] = field(default_factory=list[CurrentRate])
    # Cómo vas en las categorías del mensaje (Fase 12); vacío si está apagado o sin datos.
    context: list[ContextLine] = field(default_factory=list[ContextLine])


@dataclass(frozen=True, slots=True)
class NeedsCurrency:
    token: str
    drafts: list[TransactionDraft]  # todos los del mensaje; los dudosos con `needs_currency`


Outcome = (
    Saved
    | NeedsCurrency
    | ExchangeSaved
    | QueryAnswer
    | CorrectionOutcome
    | DebtOutcome
    | DebtList
    | BudgetOutcome
    | BudgetStatus
    | Ask
    | NotATransaction
)


@dataclass(frozen=True, slots=True)
class _Followup:
    """La última pregunta del bot, para completar el mensaje con la próxima respuesta."""

    raw_text: str
    question: str
    expires_at: datetime


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
        exchanges: ExchangeService,
        queries: QueryService,
        corrections: CorrectionService,
        debts: DebtService,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        *,
        budgets: BudgetService | None = None,
        context: ContextSource | None = None,
    ) -> None:
        self._store = store
        self._extractor = extractor
        self._rates = rates
        self._exchanges = exchanges
        self._queries = queries
        self._corrections = corrections
        self._debts = debts
        self._budgets = budgets
        self._context = context
        self._clock = clock
        self._pending = PendingStore(clock)
        self._followups: dict[UUID, _Followup] = {}

    async def correct_text(self, user: User, text: str) -> Outcome:
        """`/corregir <texto>`: el texto se interpreta sabiendo que es una corrección."""
        self._followups.pop(user.id, None)
        outcome = await self._interpret(
            user, f"Corrige el último movimiento: {text}", None, text, only_correction=True
        )
        if isinstance(outcome, Ask):
            self._followups[user.id] = _Followup(
                text, outcome.question, self._clock() + FOLLOWUP_TTL
            )
        return outcome

    async def runway(self, user: User) -> RunwayAnswer:
        """/colchon: cuántos días te dura lo que tienes (Fase 12)."""
        return await self._queries.runway(user, self._clock().astimezone(ZoneInfo(user.timezone)))

    async def last_movements(self, user: User) -> list[SavedTransaction] | NothingToCorrect:
        return await self._corrections.last(user)

    async def register_text(self, user: User, text: str) -> Outcome:
        """Interpreta el mensaje; si responde a la última pregunta del bot, lo junta con ella."""
        followup = self._followups.pop(user.id, None)
        previous = None
        raw_text = text
        if followup is not None and followup.expires_at > self._clock():
            previous = (followup.raw_text, followup.question)
            raw_text = f"{followup.raw_text} / {text}"
        outcome = await self._interpret(user, text, previous, raw_text)
        if isinstance(outcome, Ask):
            self._followups[user.id] = _Followup(
                raw_text, outcome.question, self._clock() + FOLLOWUP_TTL
            )
        return outcome

    async def _interpret(
        self,
        user: User,
        text: str,
        previous: tuple[str, str] | None,
        raw_text: str,
        *,
        only_correction: bool = False,
    ) -> Outcome:
        now_local = self._clock().astimezone(ZoneInfo(user.timezone))
        categories = await self._store.categories(user.id)
        names = _category_names(categories)
        examples = await self._corrections.examples(user)
        extraction = await self._extractor.extract(text, names, now_local, previous, examples)

        # `/corregir` nunca anota ni consulta: si el LLM lo leyó como otra cosa
        # («/corregir almuerzo 20 bs» → un gasto nuevo), se pregunta en vez de duplicar.
        if only_correction and (extraction.intent != "correction" or not extraction.correction):
            return Ask(WHAT_TO_FIX)

        # Al completar un cambio pendiente el LLM a veces lo etiqueta como corrección.
        completes_exchange = previous is not None and extraction.exchange is not None
        if extraction.intent == "log_exchange" or completes_exchange:
            if extraction.exchange is None:
                return Ask("¿Qué moneda cambiaste, cuánto y a qué tasa?")
            draft = to_exchange_draft(extraction.exchange, now_local)
            return await self._exchanges.register(user, draft, raw_text)
        if extraction.intent == "log_debt":
            if extraction.debt is None:
                return Ask("¿Quién le debe a quién, cuánto y en qué moneda?")
            debt = to_debt_draft(extraction.debt, names)
            return await self._debts.register(user, debt, raw_text)
        if extraction.intent == "settle_debt":
            if extraction.debt_payment is None:
                return Ask("¿Qué deuda se pagó? Dime con quién y cuánto.")
            payment = to_payment_draft(extraction.debt_payment)
            return await self._debts.settle(user, payment, raw_text)
        if extraction.intent == "set_budget" and self._budgets is not None:
            if extraction.budget is None:
                return Ask("¿En qué categoría quieres el tope y de cuánto al mes?")
            return await self._budgets.apply(user, to_budget_draft(extraction.budget), raw_text)
        if extraction.intent == "query" and extraction.query is not None:
            query = extraction.query
            if query.tool == "budget_status" and self._budgets is not None:
                return await self._budgets.status(user)
            if query.tool == "budget_status":
                return NotATransaction("query")  # sin servicio de topes (pruebas viejas)
            if query.tool == "list_debts":
                return await self._debts.list(
                    user,
                    direction=query.direction,
                    counterparty=query.counterparty,
                    include_settled=query.include_settled,
                )
            return await self._queries.answer(user, query, now_local)
        if extraction.intent == "correction" and extraction.correction is not None:
            draft = to_correction_draft(extraction.correction)
            return await self._corrections.correct(user, draft, raw_text)
        if extraction.intent == "set_budget":
            return NotATransaction("other")  # sin servicio de topes (pruebas viejas)
        if extraction.intent != "log_transactions":
            return NotATransaction(extraction.intent)
        if extraction.clarification and extraction.clarification.field != "currency":
            return Ask(extraction.clarification.question)
        drafts = to_drafts(extraction.transactions, names, now_local)
        if not drafts:
            return Ask("No encontré ningún monto. ¿Cuánto fue y en qué?")
        if any(d.needs_currency for d in drafts):
            pending = _Pending(
                user.id, drafts, raw_text, extraction.confidence, self._clock() + PENDING_TTL
            )
            return NeedsCurrency(self._pending.put(pending), drafts)
        return await self._save(user, drafts, raw_text, extraction.confidence, categories)

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

    async def undo_exchange(self, user: User, exchange_id: UUID) -> int:
        return await self._exchanges.undo(user, exchange_id)

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
        replaced = [c for c in rates.values() if c is not None and c.replaced is not None]
        result = Saved(saved, stale, replaced)
        if self._context is not None:
            result = replace(result, context=await self._context.lines(user, saved))
        return result


def _category_names(categories: Sequence[Category]) -> Categories:
    """Las que el LLM puede elegir: sin las de deudas, que solo usa la liquidación."""
    usable = [c for c in categories if c.name not in DEBT_CATEGORIES]
    return Categories(
        expense=[c.name for c in usable if c.kind == "expense"],
        income=[c.name for c in usable if c.kind == "income"],
    )


def _category_for(categories: Sequence[Category], draft: TransactionDraft) -> Category:
    wanted = draft.category or FALLBACK_CATEGORY[draft.kind]
    for name in (wanted, FALLBACK_CATEGORY[draft.kind]):
        for category in categories:
            if category.kind == draft.kind and category.name == name:
                return category
    raise LookupError(f"no existe la categoría de respaldo {FALLBACK_CATEGORY[draft.kind]!r}")
