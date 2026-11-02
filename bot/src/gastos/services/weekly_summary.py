"""Caso de uso: el resumen semanal, a pedido (/resumen) y automático el domingo en la tarde.

1. Las métricas se calculan en código (`domain.metrics`) con datos de la BD.
2. Se escriben como frases con cifras ya formateadas (`facts`): son la plantilla de respaldo
   y, en JSON, lo único que recibe el LLM.
3. El LLM las redacta en 4–6 líneas. Si el texto trae un número que no está en las frases,
   o el LLM no responde, se envía la plantilla: el resumen nunca falla ni inventa cifras.

El envío automático reserva la semana en `weekly_summaries` antes de mandar, así que un
reinicio o una corrida repetida del programador no duplican el mensaje (ADR 0008).
"""

import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Final, Literal, Protocol
from uuid import UUID
from zoneinfo import ZoneInfo

import structlog
from pydantic import BaseModel, Field

from gastos.domain.conversion import Rate, units_per_usd
from gastos.domain.currency import Currency, QuotedCurrency
from gastos.domain.errors import LLMUnavailable, RateUnavailable
from gastos.domain.metrics import (
    BolivarPower,
    WeeklyMetrics,
    WeekWindow,
    bolivar_power,
    week_window,
    weekly_metrics,
)
from gastos.domain.money import format_money, format_number
from gastos.domain.numbers import unknown_numbers
from gastos.domain.reports import AccountBalance, CategoryTotal, CurrencyTotal
from gastos.domain.transaction import TransactionKind
from gastos.domain.user import User
from gastos.llm.base import LLMClient
from gastos.services.rates import CurrentRate

log = structlog.get_logger()

SUMMARY_PROMPT_VERSION: Final = "resumen-v1"
SUNDAY: Final = 6  # datetime.weekday()
MAX_TEXT_CHARS: Final = 1200  # más largo ya no es un resumen
VES_SOURCE_LABELS: Final = {"bcv": "BCV", "parallel": "paralelo", "p2p": "P2P"}

SYSTEM_PROMPT: Final = """\
Eres el asistente de finanzas personales de alguien que vive con bolívares, pesos
colombianos, dólares y USDT. Redactas su resumen semanal en español, con un tono cercano y
directo (tutéalo). Sin saludo ni despedida.

Recibes un JSON con frases que ya contienen todas las cifras. Reglas:
- Usa solo esos datos. No calcules, no redondees ni conviertas: copia cada cifra tal como
  viene, con su moneda y su formato (1.200,50 Bs; 12,5 %).
- No agregues cifras, fechas ni porcentajes que no estén en el JSON, ni números con letras.
- Forma: de 4 a 6 líneas cortas, una idea por línea.
- La primera línea dice, sin cifras, cómo le fue: por ejemplo, si gastó más o menos que la
  semana pasada o si fue una semana tranquila.
- Luego: cuánto gastó y en qué se le fue más, lo que le entró si viene, y qué pasó con el
  bolívar y con sus bolívares si viene. No copies las frases: redáctalas con tus palabras.
- Si el bolívar perdió valor y tiene bolívares, explica qué le costó eso; si ganó, dilo.
- Puedes cerrar con una sugerencia breve que se desprenda de los datos, sin cifras nuevas.
- Texto plano: sin Markdown, sin asteriscos, sin títulos ni viñetas. Máximo 3 emojis.

Devuelve JSON con el campo lines: la lista de líneas, en orden."""


class SummaryDraft(BaseModel):
    # Una lista y no un texto: Gemini escribía todo en un párrafo aunque se le pidieran líneas.
    lines: list[str] = Field(min_length=3, max_length=7)

    @property
    def text(self) -> str:
        return "\n".join(line.strip() for line in self.lines if line.strip())


class SummaryReports(Protocol):
    """Lo implementa db.ReportRepository."""

    async def totals(
        self,
        user_id: UUID,
        kind: TransactionKind,
        start: datetime,
        end: datetime,
        currency: Currency | None,
        category: str | None,
    ) -> list[CurrencyTotal]: ...
    async def spending_by_category(
        self, user_id: UUID, start: datetime, end: datetime, currency: Currency | None
    ) -> list[CategoryTotal]: ...
    async def account_balances(self, user_id: UUID) -> list[AccountBalance]: ...


class SummaryRates(Protocol):
    """Lo implementa services.RateService."""

    async def for_user(self, user: User, currency: QuotedCurrency) -> CurrentRate: ...
    async def for_user_at(
        self, user: User, currency: QuotedCurrency, moment: datetime
    ) -> Rate | None: ...


class SentSummaries(Protocol):
    """Lo implementa db.SummaryRepository."""

    async def claim(self, user_id: UUID, week_start: date) -> bool: ...
    async def release(self, user_id: UUID, week_start: date) -> None: ...


class Recipients(Protocol):
    """Lo implementa db.UserRepository."""

    async def onboarded(self) -> list[User]: ...


Send = Callable[[User, str], Awaitable[None]]


@dataclass(frozen=True, slots=True)
class WeeklySummary:
    metrics: WeeklyMetrics
    text: str  # el mensaje completo, listo para enviar
    written_by: Literal["llm", "template"]


# ---- Frases con las cifras: plantilla de respaldo y entrada del LLM ----


def _amounts(rows: list[CurrencyTotal]) -> str:
    return " · ".join(format_money(r.amount, r.currency) for r in rows)


def _with_usd(rows: list[CurrencyTotal], usd: Decimal) -> str:
    text = _amounts(rows)
    if any(r.currency != "USD" for r in rows):
        text += f" (≈ {format_money(usd, 'USD')})"
    return text


def _pct(value: Decimal) -> str:
    return f"{format_number(abs(value), 1)} %"


def _per_usd(rate: Rate) -> str:
    return format_number(units_per_usd(rate), 2)


def _comparison(m: WeeklyMetrics) -> str | None:
    if m.expense_change_pct is None:
        if m.expenses_usd == 0:
            return None
        return "La semana pasada a esta altura no habías anotado gastos."
    before = format_money(m.previous_expenses_usd, "USD")
    if m.expense_change_pct == 0:
        return f"Gastaste lo mismo que la semana pasada a esta altura ({before})."
    more = "más" if m.expense_change_pct > 0 else "menos"
    return (
        f"Gastaste {_pct(m.expense_change_pct)} {more} que la semana pasada a esta altura "
        f"(entonces: {before}), comparando en USD con la tasa de cada movimiento."
    )


def _bolivar_facts(b: BolivarPower, window: WeekWindow) -> list[tuple[str, str]]:
    source = VES_SOURCE_LABELS[b.source]
    since_start = b.rate_start.fetched_at <= window.start + timedelta(days=1)
    when = (
        "esta semana"
        if since_start
        else (f"desde el {b.rate_start.fetched_at.astimezone(window.start.tzinfo):%d/%m}")
    )
    if b.change_pct == 0:
        change = f"el bolívar se mantuvo {when} en {_per_usd(b.rate_now)} Bs por USD"
    else:
        verb = "perdió" if b.change_pct < 0 else "ganó"
        change = (
            f"el bolívar {verb} {_pct(b.change_pct)} de su valor en dólares {when}: "
            f"pasó de {_per_usd(b.rate_start)} a {_per_usd(b.rate_now)} Bs por USD"
        )
    facts = [("bolivar", f"Tasa {source}: {change}.")]
    if b.balance > 0 and b.change_pct != 0:
        facts.append(
            (
                "tus_bolivares",
                f"Tus {format_money(b.balance, 'VES')} valían "
                f"{format_money(b.value_start_usd, 'USD')} al empezar y hoy "
                f"{format_money(b.value_now_usd, 'USD')} "
                f"({format_money(abs(b.value_change_usd), 'USD')} "
                f"{'menos' if b.value_change_usd < 0 else 'más'}).",
            )
        )
    return facts


def facts(m: WeeklyMetrics) -> list[tuple[str, str]]:
    """Las cifras de la semana como frases (clave, frase); sin cifras inventables."""
    items: list[tuple[str, str]] = []
    if m.expenses:
        items.append(("gastos", f"Gastaste {_with_usd(m.expenses, m.expenses_usd)}."))
    else:
        items.append(("gastos", "No anotaste gastos."))
    if m.top_category is not None and m.expenses_usd > 0:
        top = m.top_category
        amounts = " · ".join(format_money(a, c) for c, a in top.amounts)
        items.append(
            (
                "categoria_principal",
                f"Donde más gastaste: {top.name}, {amounts} ({_pct(top.share_pct)} del total).",
            )
        )
    comparison = _comparison(m)
    if comparison:
        items.append(("comparacion", comparison))
    if m.income:
        items.append(("ingresos", f"Te entraron {_with_usd(m.income, m.income_usd)}."))
    if m.bolivar is not None:
        items += _bolivar_facts(m.bolivar, m.window)
    return items


def header(window: WeekWindow) -> str:
    return f"📊 Tu semana · {window.start:%d/%m}–{window.end:%d/%m}"


def template_text(m: WeeklyMetrics) -> str:
    return "\n".join(sentence for _, sentence in facts(m))


def _stale_note(current: CurrentRate | None, now: datetime) -> str | None:
    if current is None or not current.stale:
        return None
    hours = int((now - current.rate.fetched_at).total_seconds() // 3600)
    return f"⚠️ La tasa del Bs lleva {hours} h sin actualizarse; usé la última guardada."


class WeeklySummaryService:
    def __init__(
        self,
        reports: SummaryReports,
        rates: SummaryRates,
        llm: LLMClient,
        sent: SentSummaries,
        recipients: Recipients,
        *,
        send_hour: int = 18,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._reports = reports
        self._rates = rates
        self._llm = llm
        self._sent = sent
        self._recipients = recipients
        self._send_hour = send_hour
        self._clock = clock

    async def compose(self, user: User, now: datetime | None = None) -> WeeklySummary:
        now = now or self._clock()
        window = week_window(now.astimezone(ZoneInfo(user.timezone)))
        metrics, current_ves = await self._metrics(user, window)
        head = header(window)
        written_by: Literal["llm", "template"] = "template"
        body = template_text(metrics)
        if metrics.has_activity:
            written = await self._write(metrics, head)
            if written is not None:
                body, written_by = written, "llm"
        parts = [head, body]
        note = _stale_note(current_ves, now)
        if note:
            parts.append(note)
        log.info(
            "weekly_summary_composed",
            written_by=written_by,
            movements=metrics.movements,
            prompt_version=SUMMARY_PROMPT_VERSION,
        )
        return WeeklySummary(metrics, "\n\n".join(parts), written_by)

    def due_week(self, user: User, now: datetime) -> date | None:
        """El lunes de la semana cuyo resumen toca enviar ahora, o None si no toca."""
        local = now.astimezone(ZoneInfo(user.timezone))
        if local.weekday() != SUNDAY or local.hour < self._send_hour:
            return None
        return week_window(local).start.date()

    async def send_due(self, send: Send) -> int:
        """Envía el resumen a quien le toque; lo llama el programador cada pocos minutos."""
        now = self._clock()
        sent = 0
        for user in await self._recipients.onboarded():
            week = self.due_week(user, now)
            if week is None or not await self._sent.claim(user.id, week):
                continue
            try:
                summary = await self.compose(user, now)
                await send(user, summary.text)
            except Exception as exc:  # un usuario con error no frena a los demás
                await self._sent.release(user.id, week)
                log.error("weekly_summary_failed", user_id=str(user.id), error=type(exc).__name__)
                continue
            sent += 1
        if sent:
            log.info("weekly_summaries_sent", sent=sent)
        return sent

    async def _metrics(
        self, user: User, window: WeekWindow
    ) -> tuple[WeeklyMetrics, CurrentRate | None]:
        r = self._reports
        start, end = window.start, window.end
        expenses = await r.totals(user.id, "expense", start, end, None, None)
        income = await r.totals(user.id, "income", start, end, None, None)
        previous = await r.totals(
            user.id, "expense", window.previous_start, window.previous_end, None, None
        )
        categories = await r.spending_by_category(user.id, start, end, None)
        bolivar, current = await self._bolivar(user, window)
        metrics = weekly_metrics(window, expenses, income, previous, categories, bolivar)
        return metrics, current

    async def _bolivar(
        self, user: User, window: WeekWindow
    ) -> tuple[BolivarPower | None, CurrentRate | None]:
        try:
            current = await self._rates.for_user(user, "VES")
        except RateUnavailable:
            return None, None
        start = await self._rates.for_user_at(user, "VES", window.start) or current.rate
        balances = await self._reports.account_balances(user.id)
        balance = sum((b.balance for b in balances if b.currency == "VES"), Decimal(0))
        return bolivar_power(user.ves_rate_source, start, current.rate, balance), current

    async def _write(self, metrics: WeeklyMetrics, head: str) -> str | None:
        """El texto del LLM, o None si no responde o trae cifras que no están en los datos."""
        items = facts(metrics)
        payload = json.dumps(dict(items), ensure_ascii=False, indent=2)
        try:
            draft = await self._llm.structured(
                system=SYSTEM_PROMPT, prompt=payload, schema=SummaryDraft
            )
        except LLMUnavailable:
            log.warning("weekly_summary_llm_unavailable")
            return None
        text = draft.text
        unknown = unknown_numbers(text, [head, *(sentence for _, sentence in items)])
        if unknown or not text or len(text) > MAX_TEXT_CHARS:
            # Solo cuántas: las cifras son datos financieros y no van a los logs.
            log.warning("weekly_summary_rejected", unknown_numbers=len(unknown))
            return None
        return text
