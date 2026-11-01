"""Filas que devuelven las herramientas de consulta: siempre por moneda original.

Sumar Bs con USD es un error, así que ningún total mezcla monedas. El equivalente en USD
de los gastos e ingresos es la suma de sus snapshots (`amount_usd`): lo que valían al
registrarse, no al consultar.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from gastos.domain.currency import Currency
from gastos.domain.transaction import TransactionKind


@dataclass(frozen=True, slots=True)
class CurrencyTotal:
    currency: Currency
    amount: Decimal
    amount_usd: Decimal  # suma de los snapshots
    count: int


@dataclass(frozen=True, slots=True)
class CategoryTotal:
    category: str
    currency: Currency
    amount: Decimal
    amount_usd: Decimal
    count: int


@dataclass(frozen=True, slots=True)
class AccountBalance:
    account_name: str
    currency: Currency
    balance: Decimal


@dataclass(frozen=True, slots=True)
class TransactionRow:
    occurred_at: datetime
    kind: TransactionKind
    amount: Decimal
    currency: Currency
    category: str
    description: str | None
