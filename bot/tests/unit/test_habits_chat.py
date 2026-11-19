"""Textos de topes, colchón y contexto, y el colchón en el resumen semanal (Fase 12)."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from gastos.chat.answers import answer_text
from gastos.chat.handlers.budgets import (
    budget_saved_text,
    budget_status_text,
    context_text,
    progress_text,
    runway_text,
)
from gastos.chat.handlers.transactions import confirmation_text
from gastos.domain.budget import Budget, BudgetProgress
from gastos.domain.conversion import Rate, UsdSnapshot
from gastos.domain.runway import Runway, RunwayUnknown
from gastos.domain.transaction import SavedTransaction
from gastos.services.budgets import BudgetSaved, BudgetStatus
from gastos.services.context import BudgetLine, WeekLine
from gastos.services.query_tools import BalancesAnswer, RunwayAnswer
from gastos.services.transactions import Saved
from gastos.services.users import UserService
from gastos.services.weekly_summary import runway_section
from tests.fakes import FakeUserStore, make_user

D = Decimal
NOW = datetime(2026, 11, 19, 19, tzinfo=UTC)
USER = make_user(onboarded=True)
NO_BALANCES = BalancesAnswer([], True, D(0), [], [])


def progress(limit: str, spent: str, days_left: int = 12) -> BudgetProgress:
    return BudgetProgress(Budget(uuid4(), "comida", D(limit)), D(spent), days_left)


def test_progreso_del_tope_sin_juzgar() -> None:
    assert progress_text(progress("100", "62")) == (
        "comida: llevas 62,00 de 100,00 USD este mes; te quedan 38,00 USD para 12 días."
    )
    assert progress_text(progress("100", "85", 1)) == (
        "comida: llevas 85,00 de 100,00 USD este mes (85 %); te quedan 15,00 USD para 1 día."
    )
    assert progress_text(progress("100", "112")) == (
        "comida: llevas 112,00 de 100,00 USD este mes, 12,00 USD por encima del tope. "
        "Quedan 12 días del mes."
    )


def test_lineas_de_contexto() -> None:
    assert context_text(BudgetLine(progress("100", "62"))).startswith("📊 comida: llevas 62,00")
    assert context_text(WeekLine("transporte", D("12.5"), D(8))) == (
        "📊 transporte esta semana: 12,50 USD · la semana pasada a esta altura: 8,00 USD."
    )


def test_la_confirmacion_lleva_el_contexto_debajo() -> None:
    tx = SavedTransaction(
        id=uuid4(),
        kind="expense",
        amount=D(15),
        currency="USD",
        category="comida",
        description="almuerzo",
        account_name="efectivo USD",
        snapshot=UsdSnapshot(D(1), "pivot", D(15)),
        occurred_at=NOW,
    )
    saved = Saved([tx], [], context=[BudgetLine(progress("100", "62"))])
    assert confirmation_text(saved, USER, NOW) == (
        "✅ Gasto · 15,00 USD · comida · almuerzo\n"
        "📊 comida: llevas 62,00 de 100,00 USD este mes; te quedan 38,00 USD para 12 días."
    )


def test_tope_guardado_en_bolivares_y_reemplazado() -> None:
    old = Budget(uuid4(), "comida", D(80))
    saved = BudgetSaved(
        progress("40", "0"),
        replaced=old,
        converted_from=(D(20000), "VES"),
        rate=Rate("VES", "parallel", D("0.002"), NOW),
    )
    assert budget_saved_text(saved, NOW) == (
        "🎯 Tope de comida: 40,00 USD al mes (tus 20.000,00 Bs a la tasa de hoy); antes era "
        "80,00 USD.\n"
        "comida: llevas 0,00 de 40,00 USD este mes; te quedan 40,00 USD para 12 días.\n"
        "Los topes van en dólares para que no se queden viejos cuando sube el dólar."
    )


def test_estado_de_los_topes() -> None:
    assert budget_status_text(BudgetStatus([], 12)).startswith("Todavía no tienes topes.")
    text = budget_status_text(BudgetStatus([progress("100", "62")], 12))
    assert text.splitlines()[0] == "🎯 Tus topes del mes (quedan 12 días):"


def test_colchon_en_el_chat() -> None:
    answer = RunwayAnswer(Runway(D(400), D(10), 40, 90), NO_BALANCES)
    assert runway_text(answer) == (
        "🛟 Con lo que tienes (≈ 400,00 USD) cubres unos 40 días de tus gastos, a 10,00 USD al "
        "día, tu gasto promedio de los últimos 90 días.\n"
        "Siguiente escalón: 60 días.\n"
        "Lo que te deben no cuenta hasta que te lo paguen."
    )
    assert answer_text(answer, USER, NOW) == runway_text(answer)
    short = runway_text(RunwayAnswer(Runway(D(5), D(10), 0, 20), NO_BALANCES))
    assert short.startswith("🛟 Hoy lo que tienes no alcanza para un día de tus gastos")
    assert "desde que empezaste a anotar (20 días)" in short


def test_colchon_sin_datos_suficientes() -> None:
    text = runway_text(RunwayAnswer(RunwayUnknown("short_history", 4), NO_BALANCES))
    assert text.startswith("Llevas 4 días anotando.")
    missing = BalancesAnswer([], True, D(0), [], ["VES"])
    with_missing = runway_text(RunwayAnswer(Runway(D(1), D(1), 1, 90), missing))
    assert with_missing.endswith("⚠️ Sin tasa para Bs: no está incluido.")


def test_colchon_en_el_resumen_semanal() -> None:
    assert runway_section(RunwayAnswer(Runway(D(120), D(10), 12, 90), NO_BALANCES)) == (
        "🛟 Colchón: con lo que tienes cubres unos 12 días de tus gastos. "
        "Siguiente escalón: 14 días. Detalle en /colchon."
    )
    assert runway_section(RunwayAnswer(RunwayUnknown("no_history"), NO_BALANCES)) is None


async def test_contexto_se_enciende_y_se_apaga() -> None:
    store = FakeUserStore()
    users = UserService(store)
    user = await users.identify(5, "Ana")
    assert user.context_replies is True
    off = await users.toggle_context(user)
    assert off.context_replies is False
    assert (await users.toggle_context(off)).context_replies is True
