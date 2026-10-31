"""Cuentas y categorías del usuario, tal como las usa el registro de movimientos."""

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from gastos.domain.currency import Currency

AccountKind = Literal["cash", "bank", "exchange", "wallet"]


@dataclass(frozen=True, slots=True)
class Account:
    id: UUID
    name: str
    currency: Currency
    kind: AccountKind


@dataclass(frozen=True, slots=True)
class Category:
    id: UUID
    name: str
    kind: Literal["expense", "income"]


def pick_account(accounts: list[Account], currency: Currency, hint: str | None) -> Account | None:
    """La cuenta de esa moneda que menciona el texto o, si no menciona ninguna, la primera.

    Con un `hint` que no coincide con ninguna cuenta de la moneda se usa también la primera:
    equivocarse de cuenta dentro de la misma moneda no cambia los totales por moneda.
    """
    candidates = [a for a in accounts if a.currency == currency]
    if hint:
        needle = hint.strip().casefold()
        for account in candidates:
            name = account.name.casefold()
            if needle in name or name in needle:
                return account
    return candidates[0] if candidates else None
