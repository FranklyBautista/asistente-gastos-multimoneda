"""Teclados inline y datos de callback del bot."""

from collections.abc import Iterable
from typing import Final

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from gastos.domain.currency import Currency, VesRateSource


class OnboardingCallback(CallbackData, prefix="ob"):
    step: str  # "currency" | "ves" | "tz"
    value: str


CURRENCY_LABELS: Final[dict[Currency, str]] = {
    "VES": "Bolívares (Bs)",
    "COP": "Pesos (COP)",
    "USD": "Dólares (USD)",
    "USDT": "USDT",
}
VES_SOURCE_LABELS: Final[dict[VesRateSource, str]] = {
    "bcv": "BCV (oficial)",
    "parallel": "Paralelo",
    "p2p": "P2P",
}
TIMEZONE_LABELS: Final[dict[str, str]] = {
    "America/Caracas": "Caracas",
    "America/Bogota": "Bogotá",
    "Europe/Madrid": "Madrid",
    "America/New_York": "Nueva York",
}


def _keyboard(
    step: str, options: Iterable[tuple[str, str]], columns: int = 2
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for value, label in options:
        builder.button(text=label, callback_data=OnboardingCallback(step=step, value=value))
    builder.adjust(columns)
    return builder.as_markup()


def currency_keyboard() -> InlineKeyboardMarkup:
    return _keyboard("currency", CURRENCY_LABELS.items())


def ves_source_keyboard() -> InlineKeyboardMarkup:
    return _keyboard("ves", VES_SOURCE_LABELS.items(), columns=3)


def timezone_keyboard() -> InlineKeyboardMarkup:
    return _keyboard("tz", TIMEZONE_LABELS.items())


class CurrencyChoice(CallbackData, prefix="cur"):
    token: str  # pendiente en services.transactions
    currency: str


class UndoCallback(CallbackData, prefix="undo"):
    transaction_id: str


SHORT_CURRENCY_LABELS: Final[dict[Currency, str]] = {
    "VES": "Bs",
    "COP": "COP",
    "USD": "USD",
    "USDT": "USDT",
}


def choose_currency_keyboard(token: str, default: Currency) -> InlineKeyboardMarkup:
    """Las 4 monedas en una fila, con la moneda por defecto del usuario primero."""
    builder = InlineKeyboardBuilder()
    ordered: list[Currency] = [default, *(c for c in SHORT_CURRENCY_LABELS if c != default)]
    for currency in ordered:
        builder.button(
            text=SHORT_CURRENCY_LABELS[currency],
            callback_data=CurrencyChoice(token=token, currency=currency),
        )
    builder.adjust(4)
    return builder.as_markup()


def undo_keyboard(transaction_id: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="↩️ Deshacer", callback_data=UndoCallback(transaction_id=transaction_id))
    return builder.as_markup()
