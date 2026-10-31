"""Registro desde texto libre: confirmación en una línea, botones de moneda y Deshacer."""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Final
from uuid import UUID
from zoneinfo import ZoneInfo

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery, Message
from aiogram.utils.chat_action import ChatActionSender

from gastos.chat.formatting import SYMBOLS, format_age, format_money, format_number
from gastos.chat.keyboards import (
    CurrencyChoice,
    UndoCallback,
    choose_currency_keyboard,
    undo_keyboard,
)
from gastos.domain.conversion import Rate
from gastos.domain.currency import parse_currency
from gastos.domain.transaction import SavedTransaction, TransactionDraft
from gastos.domain.user import User
from gastos.services.transactions import (
    Ask,
    NeedsCurrency,
    NotATransaction,
    Saved,
    TransactionService,
)

router = Router(name="transactions")

NEEDS_ONBOARDING = "Antes de empezar, configura tu cuenta con /start."
NOT_A_TRANSACTION: Final[dict[str, str]] = {
    "log_exchange": "Todavía no sé registrar cambios entre monedas, así que no anoté nada.",
    "query": "Todavía no sé responder preguntas sobre tus gastos; muy pronto podré.",
    "correction": ("Para corregir, toca ↩️ Deshacer en la confirmación y escríbelo de nuevo."),
    "other": (
        "No vi un gasto ni un ingreso en ese mensaje. "
        "Escríbelo como «almuerzo 15 bs» o mira /ayuda."
    ),
}
EXPIRED = "Esa pregunta ya expiró y no anoté nada. Escribe el movimiento de nuevo."
UNDONE = "↩️ Deshecho, no quedó nada anotado."
ALREADY_UNDONE = "Eso ya estaba deshecho."
KIND_LABELS: Final = {"expense": "Gasto", "income": "Ingreso"}


def _plain_amount(amount: Decimal) -> str:
    return format_number(amount, 0 if amount == amount.to_integral_value() else 2)


def question_text(drafts: list[TransactionDraft]) -> str:
    doubtful = [d for d in drafts if d.needs_currency]
    if len(doubtful) == 1:
        d = doubtful[0]
        return f"¿{_plain_amount(d.amount)} en qué moneda? ({d.description})"
    lines = ["¿En qué moneda fueron estos?"]
    lines += [f"• {d.description}: {_plain_amount(d.amount)}" for d in doubtful]
    return "\n".join(lines)


def _line(tx: SavedTransaction, now_local: datetime, tz: ZoneInfo) -> str:
    parts = [KIND_LABELS[tx.kind], format_money(tx.amount, tx.currency), tx.category]
    if tx.description and tx.description != tx.category:
        parts.append(tx.description)
    occurred = tx.occurred_at.astimezone(tz)
    if occurred.date() != now_local.date():
        parts.append(occurred.strftime("%d/%m"))
    line = " · ".join(parts)
    if tx.currency != "USD":
        line += f" (≈ {format_money(tx.snapshot.amount_usd, 'USD')})"
    return line


def _stale_note(rate: Rate, now: datetime) -> str:
    return (
        f"⚠️ La tasa de {SYMBOLS[rate.currency]} lleva {format_age(now - rate.fetched_at)} "
        "sin actualizarse; usé la última guardada."
    )


def confirmation_text(saved: Saved, user: User, now: datetime) -> str:
    tz = ZoneInfo(user.timezone)
    now_local = now.astimezone(tz)
    lines = [_line(tx, now_local, tz) for tx in saved.transactions]
    text = f"✅ {lines[0]}" if len(lines) == 1 else "✅ Anotado:\n" + "\n".join(lines)
    notes = [_stale_note(rate, now) for rate in saved.stale_rates]
    return "\n\n".join([text, *notes])


@router.message(F.text & ~F.text.startswith("/"))
async def register(
    message: Message, bot: Bot, user: User, transactions: TransactionService
) -> None:
    if not user.is_onboarded:
        await message.answer(NEEDS_ONBOARDING)
        return
    async with ChatActionSender.typing(bot=bot, chat_id=message.chat.id):
        outcome = await transactions.register_text(user, message.text or "")
    match outcome:
        case Saved():
            await message.answer(
                confirmation_text(outcome, user, datetime.now(UTC)),
                reply_markup=undo_keyboard(str(outcome.transactions[0].id)),
            )
        case NeedsCurrency(token=token, drafts=drafts):
            await message.answer(
                question_text(drafts),
                reply_markup=choose_currency_keyboard(token, user.default_currency),
            )
        case Ask(question=question):
            await message.answer(question)
        case NotATransaction(intent=intent):
            await message.answer(NOT_A_TRANSACTION[intent])


@router.callback_query(CurrencyChoice.filter())
async def choose_currency(
    query: CallbackQuery,
    callback_data: CurrencyChoice,
    user: User,
    transactions: TransactionService,
) -> None:
    currency = parse_currency(callback_data.currency)
    saved = await transactions.choose_currency(user, callback_data.token, currency)
    await query.answer()
    if not isinstance(query.message, Message):
        return
    if saved is None:
        await query.message.edit_text(EXPIRED)
        return
    await query.message.edit_text(
        confirmation_text(saved, user, datetime.now(UTC)),
        reply_markup=undo_keyboard(str(saved.transactions[0].id)),
    )


@router.callback_query(UndoCallback.filter())
async def undo(
    query: CallbackQuery, callback_data: UndoCallback, user: User, transactions: TransactionService
) -> None:
    removed = await transactions.undo(user, UUID(callback_data.transaction_id))
    if removed == 0:
        await query.answer(ALREADY_UNDONE)
        return
    await query.answer()
    if isinstance(query.message, Message):
        await query.message.edit_text(f"{query.message.text}\n\n{UNDONE}", reply_markup=None)
