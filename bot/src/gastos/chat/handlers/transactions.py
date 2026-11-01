"""Registro desde texto libre: confirmación en una línea, botones de moneda y Deshacer."""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Final
from uuid import UUID
from zoneinfo import ZoneInfo

import structlog
from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery, Message
from aiogram.utils.chat_action import ChatActionSender

from gastos.chat.answers import CAN_ANSWER, answer_text
from gastos.chat.formatting import SYMBOLS, format_age, format_money, format_number
from gastos.chat.handlers.rates import LABELS
from gastos.chat.keyboards import (
    CurrencyChoice,
    UndoCallback,
    UndoExchangeCallback,
    choose_currency_keyboard,
    undo_exchange_keyboard,
    undo_keyboard,
)
from gastos.domain.conversion import Rate
from gastos.domain.currency import Currency, parse_currency
from gastos.domain.transaction import SavedTransaction, TransactionDraft
from gastos.domain.user import User
from gastos.services.exchanges import ExchangeSaved
from gastos.services.outcomes import Ask, NotATransaction
from gastos.services.query_tools import (
    BalancesAnswer,
    SpendingAnswer,
    TotalsAnswer,
    TransactionsAnswer,
    UnknownCategory,
)
from gastos.services.transactions import NeedsCurrency, Saved, TransactionService

router = Router(name="transactions")
log = structlog.get_logger()

NEEDS_ONBOARDING = "Antes de empezar, configura tu cuenta con /start."
NOT_A_TRANSACTION: Final[dict[str, str]] = {
    "transfer": (
        "Eso parece un movimiento entre cuentas de la misma moneda; "
        "todavía no registro transferencias, así que no anoté nada."
    ),
    "query": f"No entendí bien la pregunta. {CAN_ANSWER}",
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


def _rate_text(rate: Decimal, source: Currency, target: Currency, *, invert: bool) -> str:
    """Como se cotiza en la calle: la moneda débil por 1 de la fuerte ("985,00 Bs por USDT")."""
    if invert:
        rate, source, target = 1 / rate, target, source
    decimals = 4 if rate < 10 else 2
    return f"{format_number(rate, decimals)} {SYMBOLS[target]} por {SYMBOLS[source]}"


def _difference_text(diff: Decimal) -> str:
    if diff == 0:
        return "igual que la referencia"
    pct = format_number(abs(diff), 2)
    return f"recibiste {pct} % {'más' if diff > 0 else 'menos'} que con la referencia"


def exchange_text(saved: ExchangeSaved, user: User, now: datetime) -> str:
    ex = saved.exchange
    source, target, amounts = ex.from_currency, ex.to_currency, ex.amounts
    # Misma orientación para la tasa efectiva y la de referencia, para poder compararlas.
    invert = amounts.effective_rate < 1
    head = (
        f"🔁 Cambio · {format_money(amounts.from_amount, source)} → "
        f"{format_money(amounts.to_amount, target)} · a "
        f"{_rate_text(amounts.effective_rate, source, target, invert=invert)}"
    )
    tz = ZoneInfo(user.timezone)
    occurred = ex.occurred_at.astimezone(tz)
    if occurred.date() != now.astimezone(tz).date():
        head += f" · {occurred.strftime('%d/%m')}"
    lines = [head]
    if ex.reference_rate is None or saved.difference_pct is None:
        lines.append("Sin tasa de referencia guardada para comparar.")
    else:
        sources = " y ".join(LABELS[c.rate.source] for c in saved.reference_rates)
        reference = _rate_text(ex.reference_rate, source, target, invert=invert)
        lines.append(
            f"Referencia ({sources}): {reference}; {_difference_text(saved.difference_pct)}."
        )
    notes = [_stale_note(c.rate, now) for c in saved.reference_rates if c.stale]
    return "\n\n".join(["\n".join(lines), *notes])


@router.message(F.text & ~F.text.startswith("/"))
async def register(
    message: Message, bot: Bot, user: User, transactions: TransactionService
) -> None:
    if not user.is_onboarded:
        await message.answer(NEEDS_ONBOARDING)
        return
    async with ChatActionSender.typing(bot=bot, chat_id=message.chat.id):
        outcome = await transactions.register_text(user, message.text or "")
    log.info("message_answered", outcome=type(outcome).__name__)
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
        case (
            SpendingAnswer()
            | TotalsAnswer()
            | BalancesAnswer()
            | TransactionsAnswer()
            | UnknownCategory()
        ):
            await message.answer(answer_text(outcome, user, datetime.now(UTC)))
        case ExchangeSaved():
            await message.answer(
                exchange_text(outcome, user, datetime.now(UTC)),
                reply_markup=undo_exchange_keyboard(str(outcome.exchange.id)),
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


@router.callback_query(UndoExchangeCallback.filter())
async def undo_exchange(
    query: CallbackQuery,
    callback_data: UndoExchangeCallback,
    user: User,
    transactions: TransactionService,
) -> None:
    removed = await transactions.undo_exchange(user, UUID(callback_data.exchange_id))
    if removed == 0:
        await query.answer(ALREADY_UNDONE)
        return
    await query.answer()
    if isinstance(query.message, Message):
        await query.message.edit_text(f"{query.message.text}\n\n{UNDONE}", reply_markup=None)
