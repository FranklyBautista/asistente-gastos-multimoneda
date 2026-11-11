"""Correcciones del último movimiento ("eso fue transporte", "eran 20 mil pesos").

Una corrección modifica el movimiento guardado (no crea otro) y deja un registro por campo
en `corrections`. Esos registros vuelven al prompt de extracción como ejemplos, para que el
bot no repita el mismo error con ese usuario (ADR 0009).
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_EVEN, Decimal
from typing import Final, Literal
from uuid import UUID

from gastos.domain.account import Account, Category
from gastos.domain.conversion import USD_SCALE, UsdSnapshot
from gastos.domain.currency import Currency
from gastos.domain.transaction import TransactionKind

CorrectionField = Literal["category", "currency", "amount", "kind", "account"]

# Cómo se nombra cada campo en el prompt y en las respuestas.
FIELD_LABELS: Final[dict[CorrectionField, str]] = {
    "category": "categoría",
    "currency": "moneda",
    "amount": "monto",
    "kind": "tipo",
    "account": "cuenta",
}
KIND_LABELS: Final[dict[TransactionKind, str]] = {"expense": "gasto", "income": "ingreso"}


@dataclass(frozen=True, slots=True)
class StoredTransaction:
    """Un movimiento ya guardado, con lo necesario para corregirlo."""

    id: UUID
    kind: TransactionKind
    amount: Decimal
    account: Account
    category: Category
    description: str
    snapshot: UsdSnapshot
    occurred_at: datetime
    created_at: datetime
    raw_text: str | None

    @property
    def currency(self) -> Currency:
        return self.account.currency


LastActionKind = Literal["transactions", "undone", "exchange", "none"]


@dataclass(frozen=True, slots=True)
class LastBatch:
    """Lo último que anotó el usuario, que es lo único que una corrección puede tocar.

    - `transactions`: un mensaje con movimientos vigentes; van en `transactions`.
    - `undone`: el último mensaje se deshizo; corregir otro anterior sería adivinar.
    - `exchange`: lo último fue un cambio de moneda, que no se corrige por mensaje.
    - `none`: nunca anotó nada.
    """

    kind: LastActionKind
    at: datetime | None = None  # cuándo se anotó (created_at)
    transactions: tuple[StoredTransaction, ...] = ()


@dataclass(frozen=True, slots=True)
class CorrectionDraft:
    """Lo que el usuario quiere cambiar; None = no cambia."""

    category: str | None = None
    currency: Currency | None = None
    amount: Decimal | None = None
    kind: TransactionKind | None = None
    account_hint: str | None = None
    target_hint: str | None = None

    @property
    def is_empty(self) -> bool:
        return (
            self.category is None
            and self.currency is None
            and self.amount is None
            and self.kind is None
            and self.account_hint is None
        )


@dataclass(frozen=True, slots=True)
class Change:
    field: CorrectionField
    old_value: str
    new_value: str


@dataclass(frozen=True, slots=True)
class CorrectedValues:
    """El movimiento tal como queda después de corregirlo."""

    kind: TransactionKind
    amount: Decimal
    account: Account
    category: Category
    snapshot: UsdSnapshot


@dataclass(frozen=True, slots=True)
class CorrectionExample:
    """Una corrección pasada: el mensaje original y el valor correcto de un campo."""

    raw_text: str
    field: CorrectionField
    new_value: str


def pick_target(batch: Sequence[StoredTransaction], hint: str | None) -> StoredTransaction | None:
    """El movimiento a corregir dentro del último mensaje; None si hay varios y no se sabe cuál.

    Con un solo movimiento no hace falta pista. Con varios, la pista ("café") debe coincidir
    con la descripción o la categoría de exactamente uno.
    """
    if len(batch) == 1:
        return batch[0]
    if not hint:
        return None
    needle = hint.strip().casefold()
    matches = [
        tx
        for tx in batch
        if needle in tx.description.casefold()
        or tx.description.casefold() in needle
        or needle == tx.category.name.casefold()
    ]
    return matches[0] if len(matches) == 1 else None


def rescale_snapshot(amount: Decimal, snapshot: UsdSnapshot) -> UsdSnapshot:
    """Mismo tipo de cambio, otro monto: corregir "eran 20, no 15" no cambia la tasa."""
    amount_usd = (amount * snapshot.usd_per_unit).quantize(USD_SCALE, rounding=ROUND_HALF_EVEN)
    return UsdSnapshot(snapshot.usd_per_unit, snapshot.rate_source, amount_usd)


def changes_between(target: StoredTransaction, new: CorrectedValues) -> list[Change]:
    """Un cambio por campo que de verdad cambió.

    Los valores se guardan como los usa el esquema de extracción ("income", "COP", "20000"),
    porque vuelven al prompt como ejemplos; el chat los traduce al mostrarlos.
    """
    changes: list[Change] = []
    if new.kind != target.kind:
        changes.append(Change("kind", target.kind, new.kind))
    if new.account.currency != target.currency:
        changes.append(Change("currency", target.currency, new.account.currency))
    elif new.account.id != target.account.id:
        changes.append(Change("account", target.account.name, new.account.name))
    if new.amount != target.amount:
        changes.append(Change("amount", _plain(target.amount), _plain(new.amount)))
    if new.category.id != target.category.id:
        changes.append(Change("category", target.category.name, new.category.name))
    return changes


def _plain(amount: Decimal) -> str:
    """Monto sin ceros sobrantes: 20000.000000 → "20000"; 7.990000 → "7.99"."""
    normalized = amount.normalize()
    return f"{normalized:f}"
