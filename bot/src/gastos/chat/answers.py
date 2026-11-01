"""Textos de las respuestas a consultas: plantillas fijas, siempre por moneda original.

Las cifras salen tal cual de la base de datos; el LLM no redacta nada aquí. Sin datos, se
dice que no hay datos en vez de mostrar ceros.
"""

from datetime import datetime
from decimal import Decimal
from typing import Final
from zoneinfo import ZoneInfo

from gastos.chat.formatting import SYMBOLS, format_age, format_money
from gastos.chat.handlers.rates import LABELS
from gastos.domain.currency import Currency
from gastos.domain.periods import DateRange, Period
from gastos.domain.transaction import TransactionKind
from gastos.domain.user import User
from gastos.services.query_tools import (
    BalancesAnswer,
    QueryAnswer,
    SpendingAnswer,
    TotalsAnswer,
    TransactionsAnswer,
    UnknownCategory,
)

PERIOD_LABELS: Final[dict[Period, str]] = {
    "today": "hoy",
    "yesterday": "ayer",
    "this_week": "esta semana",
    "last_week": "la semana pasada",
    "last_7_days": "los últimos 7 días",
    "this_month": "este mes",
    "last_month": "el mes pasado",
    "last_30_days": "los últimos 30 días",
    "month": "en {month}",
    "this_year": "este año",
    "all_time": "desde que empezaste a registrar",
}
MONTHS: Final = (
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
)
KIND_PLURAL: Final[dict[TransactionKind, str]] = {"expense": "gastos", "income": "ingresos"}
KIND_SINGULAR: Final[dict[TransactionKind, str]] = {"expense": "Gasto", "income": "Ingreso"}
SNAPSHOT_NOTE = "con la tasa de cada movimiento al registrarlo"
CAN_ANSWER = (
    "Puedo decirte en qué gastaste, cuánto gastaste o te entró en un periodo, "
    "tus saldos y tus últimos movimientos."
)


def period_text(date_range: DateRange) -> str:
    """ "esta semana (27/10–02/11)"; los rangos sin límite claro van sin fechas."""
    start = date_range.start
    label = PERIOD_LABELS[date_range.period]
    if date_range.period == "month":
        return label.format(month=f"{MONTHS[start.month - 1]} {start.year}")
    if date_range.period == "all_time":
        return label
    if date_range.period in ("today", "yesterday"):
        return f"{label} ({start:%d/%m})"
    return f"{label} ({start:%d/%m}–{date_range.last_day:%d/%m})"


def _filters_text(
    kind: TransactionKind | None, currency: Currency | None, category: str | None
) -> str:
    parts = [KIND_PLURAL[kind] if kind else "movimientos"]
    if category:
        parts.append(f"en {category}")
    if currency:
        parts.append(f"en {SYMBOLS[currency]}")
    return " ".join(parts)


def _count(n: int) -> str:
    return "1 movimiento" if n == 1 else f"{n} movimientos"


def spending_text(answer: SpendingAnswer) -> str:
    when = period_text(answer.range)
    if not answer.rows:
        return f"No tengo gastos registrados {when}."
    by_category: dict[str, list[str]] = {}
    usd: dict[str, Decimal] = {}
    for row in answer.rows:
        by_category.setdefault(row.category, []).append(format_money(row.amount, row.currency))
        usd[row.category] = usd.get(row.category, Decimal(0)) + row.amount_usd
    lines = [f"Gastos por categoría · {when}:"]
    for category, amounts in by_category.items():
        line = f"• {category}: {' · '.join(amounts)}"
        if answer.in_usd:
            line += f" (≈ {format_money(usd[category], 'USD')})"
        lines.append(line)
    if answer.in_usd:
        total = sum(usd.values(), Decimal(0))
        lines += ["", f"Total ≈ {format_money(total, 'USD')}, {SNAPSHOT_NOTE}."]
    return "\n".join(lines)


def totals_text(answer: TotalsAnswer) -> str:
    what = _filters_text(answer.kind, answer.currency, answer.category)
    when = period_text(answer.range)
    if not answer.rows:
        return f"No tengo {what} registrados {when}."
    lines = [f"{what.capitalize()} · {when}:"]
    lines += [f"• {format_money(r.amount, r.currency)} ({_count(r.count)})" for r in answer.rows]
    if answer.in_usd:
        lines += ["", f"Total ≈ {format_money(answer.total_usd, 'USD')}, {SNAPSHOT_NOTE}."]
    return "\n".join(lines)


def balances_text(answer: BalancesAnswer, now: datetime) -> str:
    rows = [r for r in answer.rows if r.balance != 0]
    if not rows:
        return "Todas tus cuentas están en 0: todavía no hay movimientos que las muevan."
    lines = ["Saldos:"]
    lines += [f"• {r.account_name}: {format_money(r.balance, r.currency)}" for r in rows]
    if answer.total_usd is not None:
        sources = ", ".join(LABELS[c.rate.source] for c in answer.rates)
        note = f" con las tasas de hoy ({sources})" if sources else ""
        lines += ["", f"Total ≈ {format_money(answer.total_usd, 'USD')}{note}."]
        for current in answer.rates:
            if current.stale:
                age = format_age(now - current.rate.fetched_at)
                lines.append(
                    f"⚠️ La tasa de {SYMBOLS[current.rate.currency]} lleva {age} sin actualizarse."
                )
        if answer.missing_rates:
            names = ", ".join(SYMBOLS[c] for c in answer.missing_rates)
            lines.append(f"⚠️ Sin tasa para {names}: no está incluido en el total.")
    return "\n".join(lines)


def transactions_text(answer: TransactionsAnswer, user: User) -> str:
    what = _filters_text(answer.kind, answer.currency, answer.category)
    when = period_text(answer.range)
    if not answer.rows:
        return f"No encontré {what} {when}."
    tz = ZoneInfo(user.timezone)
    lines = [
        f"Últimos {what}:"
        if answer.range.period == "all_time"
        else f"{what.capitalize()} · {when}:"
    ]
    for row in answer.rows:
        parts = [
            row.occurred_at.astimezone(tz).strftime("%d/%m"),
            KIND_SINGULAR[row.kind],
            format_money(row.amount, row.currency),
            row.category,
        ]
        if row.description and row.description != row.category:
            parts.append(row.description)
        lines.append("• " + " · ".join(parts))
    return "\n".join(lines)


def unknown_category_text(answer: UnknownCategory) -> str:
    return (
        f"No tengo una categoría «{answer.name}», así que no puedo filtrar por ella. "
        f"Las que hay: {', '.join(answer.available)}."
    )


def answer_text(answer: QueryAnswer, user: User, now: datetime) -> str:
    match answer:
        case SpendingAnswer():
            return spending_text(answer)
        case TotalsAnswer():
            return totals_text(answer)
        case BalancesAnswer():
            return balances_text(answer, now)
        case TransactionsAnswer():
            return transactions_text(answer, user)
        case UnknownCategory():
            return unknown_category_text(answer)
