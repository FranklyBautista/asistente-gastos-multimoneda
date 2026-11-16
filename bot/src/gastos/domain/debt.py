"""Deudas (Fase 11, ADR 0016): lo que debes y lo que te deben, como un libro aparte.

Registrar o liquidar una deuda no mueve saldos. Solo los mueve el gasto o ingreso que se crea
al pagarla con dinero de una cuenta, en «pago de deudas» o «cobro de deudas».
"""

import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal
from typing import Final, Literal
from uuid import UUID

from gastos.domain.account import Category
from gastos.domain.conversion import UsdSnapshot
from gastos.domain.currency import Currency
from gastos.domain.transaction import MIN_CURRENCY_CONFIDENCE, TransactionKind

DebtDirection = Literal["i_owe", "owed_to_me"]
DebtStatus = Literal["open", "partial", "settled"]

# Categorías globales de los movimientos que nacen al liquidar (migración debt_categories).
# El LLM no las ve: solo las usa la liquidación.
PAYMENT_CATEGORY: Final[dict[DebtDirection, str]] = {
    "i_owe": "pago de deudas",
    "owed_to_me": "cobro de deudas",
}
DEBT_CATEGORIES: Final = frozenset(PAYMENT_CATEGORY.values())
# Pagar una deuda propia es un gasto; cobrar una que te deben, un ingreso.
PAYMENT_KIND: Final[dict[DebtDirection, TransactionKind]] = {
    "i_owe": "expense",
    "owed_to_me": "income",
}


def counterparty_key(name: str) -> str:
    """Minúsculas, sin tildes y con un solo espacio: «  Míguel  Ángel» → «miguel angel».

    Es la misma regla que la columna generada `debts.counterparty_key`; si cambia una, debe
    cambiar la otra.
    """
    decomposed = unicodedata.normalize("NFD", name.strip())
    plain = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    return re.sub(r"\s+", " ", plain.lower())


def clean_counterparty(name: str) -> str:
    """El nombre tal como se mostrará: sin espacios de más y con mayúscula inicial."""
    cleaned = re.sub(r"\s+", " ", name.strip())[:80]
    return cleaned[:1].upper() + cleaned[1:]


@dataclass(frozen=True, slots=True)
class DebtDraft:
    """Una deuda entendida del texto, todavía sin tasa ni id."""

    direction: DebtDirection
    counterparty: str
    amount: Decimal
    currency: Currency | None
    currency_confidence: float
    category: str | None = None
    description: str | None = None

    def __post_init__(self) -> None:
        if not (self.amount.is_finite() and self.amount > 0):
            raise ValueError(f"el monto debe ser positivo: {self.amount}")
        if not counterparty_key(self.counterparty):
            raise ValueError("la deuda necesita una contraparte")

    @property
    def needs_currency(self) -> bool:
        return self.currency is None or self.currency_confidence < MIN_CURRENCY_CONFIDENCE

    def with_currency(self, currency: Currency) -> "DebtDraft":
        return replace(self, currency=currency, currency_confidence=1.0)


@dataclass(frozen=True, slots=True)
class NewDebt:
    direction: DebtDirection
    counterparty: str
    currency: Currency
    amount: Decimal
    category: Category | None
    description: str | None
    snapshot: UsdSnapshot
    raw_text: str


@dataclass(frozen=True, slots=True)
class Debt:
    """Una deuda vigente (no anulada) con lo que resta, como la da la vista debt_balances."""

    id: UUID
    direction: DebtDirection
    counterparty: str
    currency: Currency
    amount: Decimal
    remaining: Decimal
    status: DebtStatus
    description: str | None
    category: str | None
    incurred_at: datetime

    @property
    def key(self) -> str:
        return counterparty_key(self.counterparty)


@dataclass(frozen=True, slots=True)
class PaymentDraft:
    """Un pago entendido del texto. `amount` None = paga todo lo pendiente."""

    direction: DebtDirection
    counterparty: str
    amount: Decimal | None
    currency: Currency | None
    account_hint: str | None = None


def same_person(wanted: str, debt: Debt) -> bool:
    """«miguel» encuentra «Miguel Ángel» y «miguel angel» encuentra «Miguel», por palabras."""
    a, b = counterparty_key(wanted), debt.key
    return a == b or b.startswith(f"{a} ") or a.startswith(f"{b} ")


def matching_debts(debts: Sequence[Debt], payment: PaymentDraft) -> list[Debt]:
    """Las deudas pendientes que puede estar pagando: misma dirección, persona y moneda."""
    return [
        d
        for d in debts
        if d.status != "settled"
        and d.direction == payment.direction
        and same_person(payment.counterparty, d)
        and (payment.currency is None or d.currency == payment.currency)
    ]


def pending_totals(debts: Sequence[Debt]) -> dict[DebtDirection, dict[Currency, Decimal]]:
    """Lo pendiente sumado por dirección y moneda original (sin convertir), sin liquidadas."""
    totals: dict[DebtDirection, dict[Currency, Decimal]] = {}
    for d in debts:
        if d.status == "settled" or d.remaining <= 0:
            continue
        by_currency = totals.setdefault(d.direction, {})
        by_currency[d.currency] = by_currency.get(d.currency, Decimal(0)) + d.remaining
    return totals
