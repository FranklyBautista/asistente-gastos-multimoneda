"""Movimientos (gastos e ingresos) antes y después de guardarse."""

from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal
from typing import Final, Literal
from uuid import UUID

from gastos.domain.account import Account, Category
from gastos.domain.conversion import UsdSnapshot
from gastos.domain.currency import Currency

TransactionKind = Literal["expense", "income"]

# Por debajo de esta confianza la moneda se pregunta en vez de adivinarse (ADR 0002).
MIN_CURRENCY_CONFIDENCE: Final = 0.8
# Categoría de respaldo cuando el texto no deja clara ninguna.
FALLBACK_CATEGORY: Final[dict[TransactionKind, str]] = {
    "expense": "otros",
    "income": "otros ingresos",
}


@dataclass(frozen=True, slots=True)
class TransactionDraft:
    """Un movimiento entendido del texto, todavía sin cuenta, tasa ni id."""

    kind: TransactionKind
    amount: Decimal
    currency: Currency | None
    currency_confidence: float
    description: str
    category: str | None = None
    account_hint: str | None = None
    occurred_at: datetime | None = None  # None = ahora

    def __post_init__(self) -> None:
        if not (self.amount.is_finite() and self.amount > 0):
            raise ValueError(f"el monto debe ser positivo: {self.amount}")
        if self.occurred_at is not None and self.occurred_at.tzinfo is None:
            raise ValueError("occurred_at debe llevar zona horaria")

    @property
    def needs_currency(self) -> bool:
        return self.currency is None or self.currency_confidence < MIN_CURRENCY_CONFIDENCE

    def with_currency(self, currency: Currency) -> "TransactionDraft":
        """La moneda que eligió el usuario: desde ahí es segura."""
        return replace(self, currency=currency, currency_confidence=1.0)


@dataclass(frozen=True, slots=True)
class NewTransaction:
    """Un borrador ya resuelto: con cuenta, categoría y snapshot de tasa, listo para guardar."""

    account: Account
    kind: TransactionKind
    amount: Decimal
    category: Category
    description: str
    snapshot: UsdSnapshot
    occurred_at: datetime | None
    raw_text: str
    parse_confidence: float

    @property
    def currency(self) -> Currency:
        return self.account.currency


@dataclass(frozen=True, slots=True)
class SavedTransaction:
    id: UUID
    kind: TransactionKind
    amount: Decimal
    currency: Currency
    category: str
    description: str
    account_name: str
    snapshot: UsdSnapshot
    occurred_at: datetime
