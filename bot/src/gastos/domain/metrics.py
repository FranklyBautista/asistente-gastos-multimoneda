"""Métricas del resumen semanal, calculadas en código a partir de lo que devuelve la BD.

Los números del resumen nunca salen del LLM: se calculan aquí y el LLM solo los redacta
(y el texto se comprueba contra estas cifras, ver `domain.numbers`).

La semana va del lunes a las 00:00 (hora local) hasta ahora, y se compara con la semana
pasada "a la misma altura": del lunes anterior hasta hace exactamente 7 días. Así el
resumen del domingo no compara una semana casi completa con una entera, ni el del miércoles
tres días con siete.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Final

from gastos.domain.conversion import Rate
from gastos.domain.currency import Currency, VesRateSource
from gastos.domain.periods import resolve_range
from gastos.domain.reports import CategoryTotal, CurrencyTotal

PCT_SCALE: Final = Decimal("0.1")
HUNDRED: Final = Decimal(100)
WEEK: Final = timedelta(days=7)


@dataclass(frozen=True, slots=True)
class WeekWindow:
    start: datetime  # lunes 00:00, hora local (incluido)
    end: datetime  # ahora (excluido)

    @property
    def previous_start(self) -> datetime:
        return self.start - WEEK

    @property
    def previous_end(self) -> datetime:
        return self.end - WEEK


def week_window(now_local: datetime) -> WeekWindow:
    """La semana en curso hasta `now_local` (que debe llevar zona horaria)."""
    return WeekWindow(resolve_range("this_week", now_local).start, now_local)


def percent_change(new: Decimal, old: Decimal) -> Decimal | None:
    """Variación en % con un decimal; None si no hay base contra la que comparar."""
    if old == 0:
        return None
    return ((new / old - 1) * HUNDRED).quantize(PCT_SCALE, rounding=ROUND_HALF_UP)


def share(part: Decimal, total: Decimal) -> Decimal:
    """Qué % del total es `part`, con un decimal (0 si el total es 0)."""
    if total == 0:
        return Decimal(0)
    return (part / total * HUNDRED).quantize(PCT_SCALE, rounding=ROUND_HALF_UP)


def _sum_usd(rows: list[CurrencyTotal]) -> Decimal:
    return sum((r.amount_usd for r in rows), Decimal(0))


@dataclass(frozen=True, slots=True)
class TopCategory:
    name: str
    amounts: list[tuple[Currency, Decimal]]  # en cada moneda original
    amount_usd: Decimal  # suma de los snapshots
    share_pct: Decimal  # del gasto total de la semana, en USD


def top_category(rows: list[CategoryTotal], total_usd: Decimal) -> TopCategory | None:
    """La categoría con más gasto, sumando sus monedas por el valor en USD al registrarse."""
    by_name: dict[str, list[CategoryTotal]] = {}
    for row in rows:
        by_name.setdefault(row.category, []).append(row)
    if not by_name:
        return None
    # Empate: gana el nombre que va primero alfabéticamente, para que el resultado sea estable.
    name, items = max(
        sorted(by_name.items()), key=lambda item: sum((r.amount_usd for r in item[1]), Decimal(0))
    )
    usd = sum((r.amount_usd for r in items), Decimal(0))
    amounts: list[tuple[Currency, Decimal]] = sorted((r.currency, r.amount) for r in items)
    return TopCategory(name, amounts, usd, share(usd, total_usd))


@dataclass(frozen=True, slots=True)
class BolivarPower:
    """Cuánto cambió lo que compran tus bolívares en dólares durante la semana."""

    source: VesRateSource
    rate_start: Rate  # la vigente al empezar la semana (o la primera guardada después)
    rate_now: Rate
    change_pct: Decimal  # variación de usd_per_unit; negativa = el Bs compra menos dólares
    balance: Decimal  # saldo actual en Bs, sumando todas las cuentas en VES
    value_start_usd: Decimal  # ese saldo a la tasa del inicio
    value_now_usd: Decimal  # ese saldo a la tasa de hoy

    @property
    def value_change_usd(self) -> Decimal:
        return self.value_now_usd - self.value_start_usd


def bolivar_power(
    source: VesRateSource, rate_start: Rate, rate_now: Rate, balance: Decimal
) -> BolivarPower:
    if rate_start.currency != "VES" or rate_now.currency != "VES":
        raise ValueError("el poder adquisitivo se mide con tasas del bolívar")
    change = percent_change(rate_now.usd_per_unit, rate_start.usd_per_unit)
    return BolivarPower(
        source=source,
        rate_start=rate_start,
        rate_now=rate_now,
        change_pct=change if change is not None else Decimal(0),
        balance=balance,
        value_start_usd=balance * rate_start.usd_per_unit,
        value_now_usd=balance * rate_now.usd_per_unit,
    )


@dataclass(frozen=True, slots=True)
class WeeklyMetrics:
    window: WeekWindow
    expenses: list[CurrencyTotal]  # por moneda original
    income: list[CurrencyTotal]
    expenses_usd: Decimal  # suma de snapshots
    income_usd: Decimal
    previous_expenses_usd: Decimal  # semana pasada a la misma altura
    expense_change_pct: Decimal | None  # None si la semana pasada no hubo gastos
    top_category: TopCategory | None
    movements: int
    bolivar: BolivarPower | None  # None si no hay tasa del Bs guardada

    @property
    def has_activity(self) -> bool:
        return self.movements > 0


def weekly_metrics(
    window: WeekWindow,
    expenses: list[CurrencyTotal],
    income: list[CurrencyTotal],
    previous_expenses: list[CurrencyTotal],
    categories: list[CategoryTotal],
    bolivar: BolivarPower | None,
) -> WeeklyMetrics:
    expenses_usd = _sum_usd(expenses)
    previous_usd = _sum_usd(previous_expenses)
    return WeeklyMetrics(
        window=window,
        expenses=expenses,
        income=income,
        expenses_usd=expenses_usd,
        income_usd=_sum_usd(income),
        previous_expenses_usd=previous_usd,
        expense_change_pct=percent_change(expenses_usd, previous_usd),
        top_category=top_category(categories, expenses_usd),
        movements=sum(r.count for r in [*expenses, *income]),
        bolivar=bolivar,
    )
