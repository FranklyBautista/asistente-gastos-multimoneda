"""Deudas en el chat (Fase 11): confirmaciones, botones para pagar, Deshacer y /deudas.

Los mensajes de deudas van en HTML de Telegram para poder tachar (<s>) las liquidadas; todo
texto que escribió el usuario (nombres, descripciones) se escapa.
"""

from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal
from html import escape
from typing import Final
from uuid import UUID
from zoneinfo import ZoneInfo

from aiogram import Router
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from gastos.chat.formatting import format_age, format_money
from gastos.chat.keyboards import (
    NO_MOVEMENT_INDEX,
    DebtAccountPick,
    DebtCurrencyChoice,
    DebtPick,
    UndoDebtCallback,
    UndoDebtPaymentCallback,
    debt_account_keyboard,
    debt_currency_keyboard,
    debt_pick_keyboard,
    undo_debt_keyboard,
    undo_debt_payment_keyboard,
)
from gastos.domain.conversion import Rate
from gastos.domain.currency import Currency, parse_currency
from gastos.domain.debt import Debt, DebtDirection
from gastos.domain.money import SYMBOLS, format_number
from gastos.domain.user import User
from gastos.services.debts import (
    ChooseAccount,
    ChooseDebt,
    DebtList,
    DebtOutcome,
    DebtSaved,
    DebtService,
    NeedsDebtCurrency,
    NoMatchingDebt,
    PaymentSaved,
)
from gastos.services.outcomes import Ask

router = Router(name="debts")

NEEDS_ONBOARDING = "Antes de empezar, configura tu cuenta con /start."
EXPIRED = "Esa pregunta ya expiró y no anoté nada. Escríbelo de nuevo."
UNDONE = "↩️ Deshecho, no quedó nada anotado."
DEBT_NOT_UNDONE = "No se puede deshacer: ya estaba anulada o tiene pagos. Deshaz primero los pagos."
ALREADY_UNDONE = "Eso ya estaba deshecho."
NO_DEBTS: Final[dict[DebtDirection | None, str]] = {
    None: "No tienes deudas pendientes. 🎉",
    "i_owe": "No le debes nada a nadie. 🎉",
    "owed_to_me": "Nadie te debe nada.",
}
HTML: Final = ParseMode.HTML


def _money(amount: Decimal, currency: Currency) -> str:
    return escape(format_money(amount, currency))


def _who(debt: Debt) -> str:
    """ "Le debes 20,00 USD a Miguel" o "Miguel te debe 20,00 USD", con lo que quede."""
    name = escape(debt.counterparty)
    money = _money(debt.amount, debt.currency)
    if debt.direction == "i_owe":
        return f"Le debes {money} a {name}"
    return f"{name} te debe {money}"


def _details(debt: Debt) -> str:
    parts = [debt.category] if debt.category else []
    if debt.description and debt.description != debt.category:
        parts.append(debt.description)
    return " · ".join(escape(p) for p in parts)


def debt_line(debt: Debt, tz: ZoneInfo) -> str:
    """Una deuda en una línea; las liquidadas, tachadas."""
    line = _who(debt)
    details = _details(debt)
    if details:
        line += f" · {details}"
    line += f" · {debt.incurred_at.astimezone(tz).strftime('%d/%m')}"
    if debt.status == "settled":
        return f"<s>{line}</s> ✔️"
    if debt.status == "partial":
        line += f" (pendiente {_money(debt.remaining, debt.currency)})"
    return line


def _stale_note(rate: Rate, now: datetime) -> str:
    return (
        f"⚠️ La tasa de {SYMBOLS[rate.currency]} lleva {format_age(now - rate.fetched_at)} "
        "sin actualizarse; usé la última guardada."
    )


def debt_saved_text(saved: DebtSaved, user: User, now: datetime) -> str:
    text = f"📒 {debt_line(saved.debt, ZoneInfo(user.timezone))}"
    if saved.stale_rate is not None:
        text += f"\n\n{_stale_note(saved.stale_rate, now)}"
    return text


def _plain(amount: Decimal) -> str:
    return format_number(amount, 0 if amount == amount.to_integral_value() else 2)


def needs_currency_text(outcome: NeedsDebtCurrency) -> str:
    d = outcome.draft
    return f"¿{_plain(d.amount)} en qué moneda? (deuda con {escape(d.counterparty)})"


def no_match_text(outcome: NoMatchingDebt, user: User) -> str:
    p = outcome.payment
    name = escape(p.counterparty)
    if p.direction == "i_owe":
        head = f"No encontré una deuda pendiente en la que le debas a {name}"
    else:
        head = f"No encontré una deuda pendiente en la que {name} te deba"
    if p.currency is not None:
        head += f" en {SYMBOLS[p.currency]}"
    lines = [f"{head}, así que no anoté nada."]
    if outcome.open_debts:
        tz = ZoneInfo(user.timezone)
        lines += ["", "Pendientes:", *(f"• {debt_line(d, tz)}" for d in outcome.open_debts)]
    elif p.direction == "owed_to_me":
        lines += ["", "Si fue un ingreso, escríbelo como «me pagaron 20 dólares»."]
    return "\n".join(lines)


def choose_debt_text(outcome: ChooseDebt) -> str:
    return f"Tienes varias deudas pendientes con {escape(outcome.payment.counterparty)}. ¿Cuál es?"


def _pick_label(debt: Debt) -> str:
    label = f"{format_money(debt.remaining, debt.currency)}"
    if debt.description:
        label += f" · {debt.description}"
    return f"{label} · {debt.incurred_at.strftime('%d/%m')}"


def choose_account_text(outcome: ChooseAccount) -> str:
    debt, money = outcome.debt, _money(outcome.amount, outcome.debt.currency)
    name = escape(debt.counterparty)
    if debt.direction == "i_owe":
        return f"Pago de {money} a {name}. ¿De qué cuenta salió el dinero?"
    return f"{name} te pagó {money}. ¿A qué cuenta entró el dinero?"


def payment_text(saved: PaymentSaved, user: User) -> str:
    debt, money = saved.debt, _money(saved.amount, saved.debt.currency)
    name = escape(debt.counterparty)
    if debt.status == "settled":
        head = f"✅ Deuda liquidada: {debt_line(debt, ZoneInfo(user.timezone))}"
    else:
        did = (
            f"Le pagaste {money} a {name}"
            if debt.direction == "i_owe"
            else (f"{name} te pagó {money}")
        )
        head = f"✅ {did}; queda pendiente {_money(debt.remaining, debt.currency)}."
    movement = saved.movement
    if movement is None:
        return f"{head}\nSin movimiento de dinero: tus saldos no cambian."
    verb = "Gasto" if movement.kind == "expense" else "Ingreso"
    return (
        f"{head}\n{verb} {_money(movement.amount, movement.currency)} · "
        f"{escape(movement.category)} · {escape(movement.account_name)}"
    )


def _totals(debts: list[Debt]) -> str:
    by_currency: dict[Currency, Decimal] = defaultdict(Decimal)
    for d in debts:
        if d.status != "settled":
            by_currency[d.currency] += d.remaining
    return " + ".join(_money(v, c) for c, v in by_currency.items())


def debt_list_text(answer: DebtList, user: User) -> str:
    tz = ZoneInfo(user.timezone)
    debts = answer.debts
    if not debts:
        text = NO_DEBTS[answer.direction]
        if answer.counterparty:
            text = f"No tienes deudas pendientes con {escape(answer.counterparty)}."
        return text
    sections: list[str] = []
    for direction, title in (("i_owe", "Debes"), ("owed_to_me", "Te deben")):
        group = [d for d in debts if d.direction == direction]
        if not group:
            continue
        total = _totals(group)
        header = f"<b>{title}</b>" + (f" (total pendiente: {total})" if total else "")
        sections.append("\n".join([header, *(f"• {debt_line(d, tz)}" for d in group)]))
    return "\n\n".join(sections)


def render(
    outcome: DebtOutcome | DebtList, user: User
) -> tuple[str, InlineKeyboardMarkup | None, ParseMode | None]:
    """Texto, botones y modo de cada resultado de deudas."""
    match outcome:
        case DebtSaved():
            text = debt_saved_text(outcome, user, datetime.now(UTC))
            return text, undo_debt_keyboard(str(outcome.debt.id)), HTML
        case NeedsDebtCurrency(token=token):
            return (
                needs_currency_text(outcome),
                debt_currency_keyboard(token, user.default_currency),
                HTML,
            )
        case NoMatchingDebt():
            return no_match_text(outcome, user), None, HTML
        case ChooseDebt(token=token, candidates=candidates):
            labels = [_pick_label(d) for d in candidates]
            return choose_debt_text(outcome), debt_pick_keyboard(token, labels), HTML
        case ChooseAccount(token=token, accounts=accounts):
            names = [a.name for a in accounts]
            return choose_account_text(outcome), debt_account_keyboard(token, names), HTML
        case PaymentSaved():
            markup = undo_debt_payment_keyboard(str(outcome.payment_id))
            return payment_text(outcome, user), markup, HTML
        case DebtList():
            return debt_list_text(outcome, user), None, HTML
        case Ask(question=question):
            return question, None, None


async def reply_debt(message: Message, outcome: DebtOutcome | DebtList, user: User) -> None:
    """Respuesta del chat para los resultados de deudas que llegan por texto libre."""
    text, markup, mode = render(outcome, user)
    await message.answer(text, parse_mode=mode, reply_markup=markup)


async def _edit(query: CallbackQuery, outcome: DebtOutcome | None, user: User) -> None:
    """Tras un botón, el mensaje de la pregunta pasa a ser la respuesta o el siguiente paso."""
    await query.answer()
    if not isinstance(query.message, Message):
        return
    if outcome is None:
        await query.message.edit_text(EXPIRED)
        return
    text, markup, mode = render(outcome, user)
    await query.message.edit_text(text, parse_mode=mode, reply_markup=markup)


@router.message(Command("deudas"))
async def list_debts(message: Message, user: User, debts: DebtService) -> None:
    if not user.is_onboarded:
        await message.answer(NEEDS_ONBOARDING)
        return
    answer = await debts.list(user)
    await message.answer(debt_list_text(answer, user), parse_mode=HTML)


@router.callback_query(DebtCurrencyChoice.filter())
async def choose_currency(
    query: CallbackQuery, callback_data: DebtCurrencyChoice, user: User, debts: DebtService
) -> None:
    currency = parse_currency(callback_data.currency)
    await _edit(query, await debts.choose_currency(user, callback_data.token, currency), user)


@router.callback_query(DebtPick.filter())
async def choose_debt(
    query: CallbackQuery, callback_data: DebtPick, user: User, debts: DebtService
) -> None:
    await _edit(
        query, await debts.choose_debt(user, callback_data.token, callback_data.index), user
    )


@router.callback_query(DebtAccountPick.filter())
async def choose_account(
    query: CallbackQuery, callback_data: DebtAccountPick, user: User, debts: DebtService
) -> None:
    index = None if callback_data.index == NO_MOVEMENT_INDEX else callback_data.index
    await _edit(query, await debts.choose_account(user, callback_data.token, index), user)


@router.callback_query(UndoDebtCallback.filter())
async def undo_debt(
    query: CallbackQuery, callback_data: UndoDebtCallback, user: User, debts: DebtService
) -> None:
    if await debts.undo_debt(user, UUID(callback_data.debt_id)) == 0:
        await query.answer(DEBT_NOT_UNDONE, show_alert=True)
        return
    await _mark_undone(query)


@router.callback_query(UndoDebtPaymentCallback.filter())
async def undo_payment(
    query: CallbackQuery, callback_data: UndoDebtPaymentCallback, user: User, debts: DebtService
) -> None:
    if await debts.undo_payment(user, UUID(callback_data.payment_id)) == 0:
        await query.answer(ALREADY_UNDONE)
        return
    await _mark_undone(query)


async def _mark_undone(query: CallbackQuery) -> None:
    await query.answer()
    if isinstance(query.message, Message):
        # html_text conserva el tachado y las negritas del mensaje original.
        await query.message.edit_text(
            f"{query.message.html_text}\n\n{UNDONE}", parse_mode=HTML, reply_markup=None
        )
