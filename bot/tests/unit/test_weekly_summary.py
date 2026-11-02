"""Resumen semanal con base de datos, tasas y LLM falsos."""

from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from gastos.domain.conversion import Rate
from gastos.domain.currency import Currency
from gastos.domain.errors import LLMUnavailable
from gastos.domain.reports import AccountBalance, CategoryTotal, CurrencyTotal
from gastos.domain.transaction import TransactionKind
from gastos.domain.user import User
from gastos.services.rates import RateService
from gastos.services.weekly_summary import (
    SUMMARY_PROMPT_VERSION,
    WeeklySummaryService,
    template_text,
)
from tests.fakes import (
    FakeLLM,
    FakeRateSources,
    FakeRateStore,
    FakeRecipients,
    FakeSentSummaries,
    make_user,
)

D = Decimal
# Domingo 1 de noviembre, 18:00 en Caracas (UTC−4).
NOW = datetime(2026, 11, 1, 22, tzinfo=UTC)
WEEK_START = datetime(2026, 10, 26, 4, tzinfo=UTC)  # lunes 00:00 en Caracas
USER = make_user(onboarded=True)  # Caracas, Bs con tasa paralela

EXPENSES = [CurrencyTotal("COP", D(20000), D(5), 1), CurrencyTotal("VES", D(4000), D(9), 3)]
INCOME = [CurrencyTotal("USDT", D(200), D("199.8"), 1)]
PREVIOUS = [CurrencyTotal("USD", D(10), D(10), 2)]
CATEGORIES = [
    CategoryTotal("comida", "VES", D(4000), D(9), 3),
    CategoryTotal("transporte", "COP", D(20000), D(5), 1),
]
BALANCES = [
    AccountBalance("banesco", "VES", D(6000)),
    AccountBalance("efectivo Bs", "VES", D(4000)),
    AccountBalance("efectivo USD", "USD", D(50)),
]
# 400 Bs por USD el domingo anterior y 500 hoy.
RATE_START = Rate("VES", "parallel", D("0.0025"), datetime(2026, 10, 25, 20, tzinfo=UTC))
RATE_NOW = Rate("VES", "parallel", D("0.002"), NOW - timedelta(minutes=30))

TEMPLATE = [
    "Gastaste 20.000 COP · 4.000,00 Bs (≈ 14,00 USD).",
    "Donde más gastaste: comida, 4.000,00 Bs (64,3 % del total).",
    "Gastaste 40,0 % más que la semana pasada a esta altura (entonces: 10,00 USD), "
    "comparando en USD con la tasa de cada movimiento.",
    "Te entraron 200,00 USDT (≈ 199,80 USD).",
    "Tasa paralelo: el bolívar perdió 20,0 % de su valor en dólares esta semana: "
    "pasó de 400,00 a 500,00 Bs por USD.",
    "Tus 10.000,00 Bs valían 25,00 USD al empezar y hoy 20,00 USD (5,00 USD menos).",
]


class Reports:
    """Responde según el tipo de movimiento y el inicio del rango, como haría la BD."""

    def __init__(self, *, empty: bool = False) -> None:
        self.empty = empty
        self.ranges: list[tuple[str, datetime, datetime]] = []

    async def totals(
        self,
        user_id: UUID,
        kind: TransactionKind,
        start: datetime,
        end: datetime,
        currency: Currency | None,
        category: str | None,
    ) -> list[CurrencyTotal]:
        self.ranges.append((kind, start, end))
        if self.empty:
            return []
        if start < WEEK_START:
            return PREVIOUS
        return EXPENSES if kind == "expense" else INCOME

    async def spending_by_category(
        self, user_id: UUID, start: datetime, end: datetime, currency: Currency | None
    ) -> list[CategoryTotal]:
        return [] if self.empty else CATEGORIES

    async def account_balances(self, user_id: UUID) -> list[AccountBalance]:
        return BALANCES


def rate_service(*rates: Rate) -> RateService:
    unused = RuntimeError("no se refresca en estas pruebas")
    sources = FakeRateSources(dolarapi=unused, p2p=unused, cop=unused, usdt=unused)
    return RateService(FakeRateStore(*rates), sources, timedelta(hours=6), clock=lambda: NOW)


def service(
    *llm_responses: dict[str, Any] | Exception,
    reports: Reports | None = None,
    rates: tuple[Rate, ...] = (RATE_START, RATE_NOW),
    users: tuple[User, ...] = (USER,),
    sent: FakeSentSummaries | None = None,
    clock: Callable[[], datetime] = lambda: NOW,
) -> tuple[WeeklySummaryService, FakeLLM]:
    llm = FakeLLM(*llm_responses)
    summaries = WeeklySummaryService(
        reports or Reports(),
        rate_service(*rates),
        llm,
        sent or FakeSentSummaries(),
        FakeRecipients(*users),
        send_hour=18,
        clock=clock,
    )
    return summaries, llm


GOOD_LINES = [
    "Semana más cara que la anterior. 📈",
    "Gastaste 20.000 COP y 4.000,00 Bs, unos 14,00 USD; casi todo en comida (64,3 %).",
    "Fue un 40,0 % más que la semana pasada a esta altura.",
    " Te entraron 200,00 USDT. ",
    "El bolívar perdió 20,0 %: tus bolívares pasaron de 25,00 USD a 20,00 USD.",
]
GOOD_TEXT = "\n".join(line.strip() for line in GOOD_LINES)
GOOD = {"lines": GOOD_LINES}


async def test_metricas_de_la_semana_en_la_zona_del_usuario() -> None:
    reports = Reports()
    summaries, _ = service(GOOD, reports=reports)
    summary = await summaries.compose(USER, NOW)
    assert ("expense", WEEK_START, NOW) in reports.ranges
    # La semana pasada, a la misma altura: del lunes anterior a hace 7 días.
    assert ("expense", WEEK_START - timedelta(days=7), NOW - timedelta(days=7)) in reports.ranges
    assert summary.metrics.expense_change_pct == D("40.0")


async def test_plantilla_con_las_cifras_formateadas() -> None:
    summaries, _ = service(LLMUnavailable("caído"))
    summary = await summaries.compose(USER, NOW)
    assert template_text(summary.metrics).splitlines() == TEMPLATE


async def test_redaccion_del_llm_con_cifras_verificadas() -> None:
    summaries, llm = service(GOOD)
    summary = await summaries.compose(USER, NOW)
    assert summary.written_by == "llm"
    assert summary.text == f"📊 Tu semana · 26/10–01/11\n\n{GOOD_TEXT}"
    system, prompt = llm.calls[0]
    assert "copia cada cifra" in system
    # El LLM solo recibe las frases ya calculadas; nada de filas ni ids.
    assert '"gastos": "Gastaste 20.000 COP · 4.000,00 Bs (≈ 14,00 USD)."' in prompt
    assert str(USER.id) not in prompt
    assert SUMMARY_PROMPT_VERSION == "resumen-v1"


async def test_cifra_inventada_se_reemplaza_por_la_plantilla() -> None:
    invented = {"lines": [line.replace("14,00 USD", "15,30 USD") for line in GOOD_LINES]}
    summaries, _ = service(invented)
    summary = await summaries.compose(USER, NOW)
    assert summary.written_by == "template"
    assert "15,30" not in summary.text
    assert summary.text.splitlines()[2:] == TEMPLATE


async def test_sin_llm_se_envia_la_plantilla() -> None:
    summaries, _ = service(LLMUnavailable("caído"))
    summary = await summaries.compose(USER, NOW)
    assert summary.written_by == "template"
    assert TEMPLATE[0] in summary.text


async def test_semana_sin_movimientos_no_llama_al_llm() -> None:
    summaries, llm = service(reports=Reports(empty=True))
    summary = await summaries.compose(USER, NOW)
    assert llm.calls == []
    assert summary.text.splitlines()[2] == "No anotaste gastos."
    assert "perdió 20,0 %" in summary.text  # el bolívar se informa igual


async def test_sin_tasa_del_bolivar_se_omite_esa_parte() -> None:
    summaries, _ = service(LLMUnavailable("caído"), rates=())
    summary = await summaries.compose(USER, NOW)
    assert summary.metrics.bolivar is None
    assert "bolívar" not in summary.text


async def test_historial_que_empieza_a_mitad_de_semana() -> None:
    wednesday = replace(RATE_START, fetched_at=datetime(2026, 10, 28, 16, tzinfo=UTC))
    summaries, _ = service(LLMUnavailable("caído"), rates=(wednesday, RATE_NOW))
    summary = await summaries.compose(USER, NOW)
    assert "desde el 28/10" in summary.text


async def test_aviso_si_la_tasa_del_bolivar_esta_vieja() -> None:
    old = replace(RATE_NOW, fetched_at=NOW - timedelta(hours=9))
    summaries, _ = service(LLMUnavailable("caído"), rates=(RATE_START, old))
    summary = await summaries.compose(USER, NOW)
    assert summary.text.endswith(
        "⚠️ La tasa del Bs lleva 9 h sin actualizarse; usé la última guardada."
    )


# ---- Envío automático ----


def test_toca_el_domingo_desde_la_hora_configurada_en_la_zona_del_usuario() -> None:
    summaries, _ = service()
    bogota = replace(USER, timezone="America/Bogota")  # UTC−5: allá son las 17:00
    assert summaries.due_week(USER, NOW) == WEEK_START.astimezone(UTC).date()
    assert summaries.due_week(bogota, NOW) is None
    assert summaries.due_week(bogota, NOW + timedelta(hours=1)) is not None
    assert summaries.due_week(USER, NOW - timedelta(minutes=1)) is None  # 17:59
    assert summaries.due_week(USER, NOW - timedelta(days=1)) is None  # sábado


async def test_envia_una_sola_vez_por_semana() -> None:
    pending = make_user(222)  # sin onboarding: no recibe nada
    sent = FakeSentSummaries()
    summaries, _ = service(GOOD, users=(USER, pending), sent=sent)
    messages: list[tuple[int, str]] = []

    async def send(user: User, text: str) -> None:
        messages.append((user.telegram_id, text))

    assert await summaries.send_due(send) == 1
    assert await summaries.send_due(send) == 0  # la siguiente corrida no lo repite
    assert [telegram_id for telegram_id, _ in messages] == [USER.telegram_id]


async def test_si_el_envio_falla_se_libera_para_reintentar() -> None:
    other = make_user(333, onboarded=True)
    sent = FakeSentSummaries()
    down = LLMUnavailable("caído")
    summaries, _ = service(down, down, users=(USER, other), sent=sent)
    delivered: list[int] = []

    async def flaky(user: User, text: str) -> None:
        if user.telegram_id == USER.telegram_id:
            raise RuntimeError("Telegram no responde")
        delivered.append(user.telegram_id)

    assert await summaries.send_due(flaky) == 1
    assert delivered == [333]  # el error de uno no frena a los demás
    assert sent.released == [(USER.id, WEEK_START.date())]
    assert (USER.id, WEEK_START.date()) not in sent.claimed


async def test_texto_demasiado_largo_se_reemplaza_por_la_plantilla() -> None:
    summaries, _ = service({"lines": ["Semana tranquila. " * 30] * 3})
    summary = await summaries.compose(USER, NOW)
    assert summary.written_by == "template"
