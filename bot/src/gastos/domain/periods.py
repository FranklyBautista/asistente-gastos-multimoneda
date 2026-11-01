"""Rangos de fechas de las consultas, resueltos en código y en la zona horaria del usuario.

El LLM solo elige un periodo de una lista cerrada ("this_week", "month" con su número...);
las fechas exactas salen de aquí, porque "esta semana" depende de la zona horaria y los LLM
se equivocan con las fechas. Los rangos son semiabiertos: [start, end).
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Final, Literal

Period = Literal[
    "today",
    "yesterday",
    "this_week",
    "last_week",
    "last_7_days",
    "this_month",
    "last_month",
    "last_30_days",
    "month",  # un mes concreto: "en octubre"
    "this_year",
    "all_time",
]

PERIODS: Final[tuple[Period, ...]] = (
    "today",
    "yesterday",
    "this_week",
    "last_week",
    "last_7_days",
    "this_month",
    "last_month",
    "last_30_days",
    "month",
    "this_year",
    "all_time",
)
# Antes de esta fecha no puede haber movimientos: es el inicio de "desde siempre".
_EPOCH_YEAR: Final = 2000


@dataclass(frozen=True, slots=True)
class DateRange:
    period: Period
    start: datetime  # incluido
    end: datetime  # excluido

    @property
    def last_day(self) -> datetime:
        """El último día que cubre el rango (para mostrarlo)."""
        return self.end - timedelta(days=1)


def _midnight(moment: datetime) -> datetime:
    return moment.replace(hour=0, minute=0, second=0, microsecond=0)


def _month_start(year: int, month: int, like: datetime) -> datetime:
    return like.replace(year=year, month=month, day=1, hour=0, minute=0, second=0, microsecond=0)


def _next_month(start: datetime) -> datetime:
    if start.month == 12:
        return start.replace(year=start.year + 1, month=1)
    return start.replace(month=start.month + 1)


def resolve_range(
    period: Period, now_local: datetime, month: int | None = None, year: int | None = None
) -> DateRange:
    """Fechas exactas de un periodo. La semana empieza el lunes.

    `month` (1–12) solo se usa con "month"; sin `year`, es la última vez que ese mes empezó
    (en enero, "diciembre" es el del año pasado).
    """
    if now_local.tzinfo is None:
        raise ValueError("now_local debe llevar zona horaria")
    today = _midnight(now_local)
    tomorrow = today + timedelta(days=1)
    week_start = today - timedelta(days=today.weekday())
    month_start = today.replace(day=1)
    match period:
        case "today":
            return DateRange(period, today, tomorrow)
        case "yesterday":
            return DateRange(period, today - timedelta(days=1), today)
        case "this_week":
            return DateRange(period, week_start, week_start + timedelta(days=7))
        case "last_week":
            return DateRange(period, week_start - timedelta(days=7), week_start)
        case "last_7_days":
            return DateRange(period, tomorrow - timedelta(days=7), tomorrow)
        case "this_month":
            return DateRange(period, month_start, _next_month(month_start))
        case "last_month":
            previous = (month_start - timedelta(days=1)).replace(day=1)
            return DateRange(period, previous, month_start)
        case "last_30_days":
            return DateRange(period, tomorrow - timedelta(days=30), tomorrow)
        case "month":
            if month is None or not 1 <= month <= 12:
                raise ValueError(f"mes inválido: {month}")
            if year is None:
                year = now_local.year if month <= now_local.month else now_local.year - 1
            start = _month_start(year, month, now_local)
            return DateRange(period, start, _next_month(start))
        case "this_year":
            start = _month_start(now_local.year, 1, now_local)
            return DateRange(period, start, start.replace(year=start.year + 1))
        case "all_time":
            return DateRange(period, _month_start(_EPOCH_YEAR, 1, now_local), tomorrow)
