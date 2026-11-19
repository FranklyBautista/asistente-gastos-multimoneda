"""Hábitos en el chat (Fase 12): topes, colchón en días y la línea de contexto al anotar.

Todas las cifras salen de la base de datos y se escriben con plantillas fijas. El tono
describe sin juzgar: «llevas 112 de 100», nunca «te pasaste» (informe de investigación,
sección 2: los mensajes que suenan a regaño hacen que la gente deje de mirar sus números).
"""

from datetime import datetime
from decimal import Decimal
from typing import Final
from uuid import UUID

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from gastos.chat.formatting import SYMBOLS, format_age, format_money, format_number
from gastos.chat.keyboards import UndoBudgetCallback
from gastos.domain.budget import BudgetProgress
from gastos.domain.runway import Runway, RunwayUnknown
from gastos.domain.user import User
from gastos.services.budgets import (
    BudgetRemoved,
    BudgetSaved,
    BudgetService,
    BudgetStatus,
    NoBudget,
)
from gastos.services.context import BudgetLine, ContextLine, WeekLine
from gastos.services.query_tools import RunwayAnswer
from gastos.services.transactions import TransactionService
from gastos.services.users import UserService

router = Router(name="budgets")

NEEDS_ONBOARDING = "Antes de empezar, configura tu cuenta con /start."
UNDONE = "↩️ Deshecho: el tope quedó como estaba."
ALREADY_UNDONE = "Eso ya estaba deshecho o lo cambiaste después."
NO_BUDGETS = (
    "Todavía no tienes topes. Escríbeme, por ejemplo: «no quiero gastar más de 100 dólares al "
    "mes en comida». Te aviso cómo vas cada vez que anotes un gasto de esa categoría."
)
CONTEXT_ON = "Listo: cuando anotes un gasto te digo cómo vas en esa categoría. /contexto lo apaga."
CONTEXT_OFF = "Listo: ya no te digo cómo vas al anotar. /contexto lo vuelve a encender."
DEBTS_NOTE: Final = "Lo que te deben no cuenta hasta que te lo paguen."


def _usd(amount: Decimal) -> str:
    return format_money(amount, "USD")


def _number(amount: Decimal) -> str:
    return format_number(amount, 2)


def _days(n: int) -> str:
    return "1 día" if n == 1 else f"{n} días"


def progress_text(progress: BudgetProgress) -> str:
    """ "comida: llevas 62,00 de 100,00 USD este mes; te quedan 38,00 USD para 12 días"."""
    budget = progress.budget
    head = (
        f"{budget.category}: llevas {_number(progress.spent_usd)} de "
        f"{_usd(budget.limit_usd)} este mes"
    )
    days = _days(progress.days_left)
    match progress.state:
        case "over":
            above = _usd(progress.spent_usd - budget.limit_usd)
            return f"{head}, {above} por encima del tope. Quedan {days} del mes."
        case "near":
            return (
                f"{head} ({format_number(progress.used_pct, 0)} %); te quedan "
                f"{_usd(progress.remaining_usd)} para {days}."
            )
        case "ok":
            return f"{head}; te quedan {_usd(progress.remaining_usd)} para {days}."


def context_text(line: ContextLine) -> str:
    match line:
        case BudgetLine(progress=progress):
            return f"📊 {progress_text(progress)}"
        case WeekLine(category=category, week_usd=week, previous_usd=previous):
            return (
                f"📊 {category} esta semana: {_usd(week)} · la semana pasada a esta altura: "
                f"{_usd(previous)}."
            )


def budget_saved_text(saved: BudgetSaved, now: datetime) -> str:
    budget = saved.progress.budget
    head = f"🎯 Tope de {budget.category}: {_usd(budget.limit_usd)} al mes"
    if saved.converted_from is not None:
        amount, currency = saved.converted_from
        head += f" (tus {format_money(amount, currency)} a la tasa de hoy)"
    if saved.replaced is not None:
        head += f"; antes era {_usd(saved.replaced.limit_usd)}"
    lines = [f"{head}.", progress_text(saved.progress)]
    lines.append("Los topes van en dólares para que no se queden viejos cuando sube el dólar.")
    if saved.stale_rate and saved.rate is not None:
        age = format_age(now - saved.rate.fetched_at)
        lines.append(
            f"⚠️ La tasa de {SYMBOLS[saved.rate.currency]} lleva {age} sin actualizarse; "
            "usé la última guardada."
        )
    return "\n".join(lines)


def budget_removed_text(removed: BudgetRemoved) -> str:
    budget = removed.budget
    return f"Quité el tope de {budget.category} ({_usd(budget.limit_usd)} al mes)."


def no_budget_text(outcome: NoBudget) -> str:
    return f"No tenías un tope en {outcome.category}, así que no cambié nada."


def budget_status_text(status: BudgetStatus) -> str:
    if not status.rows:
        return NO_BUDGETS
    lines = [f"🎯 Tus topes del mes (quedan {_days(status.days_left)}):"]
    lines += [f"• {progress_text(p)}" for p in status.rows]
    return "\n".join(lines)


def _window_text(days: int) -> str:
    if days >= 90:
        return "tu gasto promedio de los últimos 90 días"
    return f"tu gasto promedio desde que empezaste a anotar ({_days(days)})"


def runway_text(answer: RunwayAnswer) -> str:
    result = answer.result
    if isinstance(result, RunwayUnknown):
        match result.reason:
            case "no_history":
                return (
                    "Todavía no tienes movimientos anotados. Cuando lleves dos semanas "
                    "anotando, te digo para cuántos días te alcanza lo que tienes."
                )
            case "short_history":
                return (
                    f"Llevas {_days(result.history_days)} anotando. Con dos semanas de "
                    "gastos te digo para cuántos días te alcanza lo que tienes."
                )
            case "no_expenses":
                return (
                    f"No anotaste gastos en {_days(result.history_days)}, así que todavía "
                    "no puedo calcular para cuántos días te alcanza lo que tienes."
                )
    lines = [_runway_head(result)]
    if result.next_step is not None:
        lines.append(f"Siguiente escalón: {_days(result.next_step)}.")
    lines.append(DEBTS_NOTE)
    if answer.balances.missing_rates:
        names = ", ".join(SYMBOLS[c] for c in answer.balances.missing_rates)
        lines.append(f"⚠️ Sin tasa para {names}: no está incluido.")
    return "\n".join(lines)


def _runway_head(result: Runway) -> str:
    pace = f"{_usd(result.daily_spend_usd)} al día, {_window_text(result.window_days)}"
    if result.days == 0:
        return f"🛟 Hoy lo que tienes no alcanza para un día de tus gastos ({pace})."
    return (
        f"🛟 Con lo que tienes (≈ {_usd(result.available_usd)}) cubres unos "
        f"{_days(result.days)} de tus gastos, a {pace}."
    )


@router.message(Command("topes"))
async def list_budgets(message: Message, user: User, budgets: BudgetService) -> None:
    if not user.is_onboarded:
        await message.answer(NEEDS_ONBOARDING)
        return
    await message.answer(budget_status_text(await budgets.status(user)))


@router.message(Command("colchon", "colchón"))
async def runway(message: Message, user: User, transactions: TransactionService) -> None:
    if not user.is_onboarded:
        await message.answer(NEEDS_ONBOARDING)
        return
    await message.answer(runway_text(await transactions.runway(user)))


@router.message(Command("contexto"))
async def toggle_context(message: Message, user: User, users: UserService) -> None:
    if not user.is_onboarded:
        await message.answer(NEEDS_ONBOARDING)
        return
    updated = await users.toggle_context(user)
    await message.answer(CONTEXT_ON if updated.context_replies else CONTEXT_OFF)


@router.callback_query(UndoBudgetCallback.filter())
async def undo_budget(
    query: CallbackQuery, callback_data: UndoBudgetCallback, user: User, budgets: BudgetService
) -> None:
    if not await budgets.undo(user, UUID(callback_data.budget_id)):
        await query.answer(ALREADY_UNDONE)
        return
    await query.answer()
    if isinstance(query.message, Message):
        await query.message.edit_text(f"{query.message.text}\n\n{UNDONE}", reply_markup=None)
