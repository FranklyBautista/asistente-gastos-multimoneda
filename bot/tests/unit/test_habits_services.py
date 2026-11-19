"""Topes, contexto al anotar y colchón en días con dobles en memoria (Fase 12)."""

from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from gastos.domain.account import Category
from gastos.domain.budget import Budget, BudgetDraft
from gastos.domain.conversion import Rate, UsdSnapshot
from gastos.domain.currency import Currency, QuotedCurrency, RateSource
from gastos.domain.reports import AccountBalance, CategoryTotal, CurrencyTotal, TransactionRow
from gastos.domain.runway import Runway, RunwayUnknown
from gastos.domain.transaction import SavedTransaction, TransactionKind
from gastos.extraction.schema import Extraction
from gastos.services.budgets import (
    BudgetRemoved,
    BudgetSaved,
    BudgetService,
    BudgetStatus,
    NoBudget,
)
from gastos.services.context import BudgetLine, ContextService, WeekLine
from gastos.services.corrections import CorrectionService
from gastos.services.debts import DebtService
from gastos.services.exchanges import ExchangeService
from gastos.services.outcomes import Ask
from gastos.services.query_tools import QueryService, RunwayAnswer, UnknownCategory
from gastos.services.rates import RateService
from gastos.services.transactions import Saved, TransactionService
from tests.fakes import (
    FakeCorrectionStore,
    FakeDebtStore,
    FakeExchangeStore,
    FakeExtractor,
    FakeRateSources,
    FakeRateStore,
    FakeReportStore,
    FakeTransactionStore,
    make_user,
)

D = Decimal
NOW = datetime(2026, 11, 19, 19, tzinfo=UTC)  # jueves 19, 15:00 en Caracas
USER = make_user(onboarded=True)
USER_TZ = ZoneInfo(USER.timezone)


@dataclass(frozen=True, slots=True)
class Expense:
    occurred_at: datetime
    category: str
    amount_usd: Decimal
    currency: Currency = "USD"


class MemoryReports:
    """Reportes que filtran de verdad por fecha y categoría, sobre una lista de gastos."""

    def __init__(self, *expenses: Expense) -> None:
        self.expenses = list(expenses)

    def _in(self, start: datetime, end: datetime, category: str | None = None) -> list[Expense]:
        return [
            e
            for e in self.expenses
            if start <= e.occurred_at < end and (category is None or e.category == category)
        ]

    async def spending_by_category(
        self, user_id: UUID, start: datetime, end: datetime, currency: Currency | None
    ) -> list[CategoryTotal]:
        totals: dict[str, Decimal] = {}
        for e in self._in(start, end):
            totals[e.category] = totals.get(e.category, D(0)) + e.amount_usd
        return [CategoryTotal(c, "USD", a, a, 1) for c, a in totals.items()]

    async def totals(
        self,
        user_id: UUID,
        kind: TransactionKind,
        start: datetime,
        end: datetime,
        currency: Currency | None,
        category: str | None,
    ) -> list[CurrencyTotal]:
        rows = self._in(start, end, category)
        if not rows:
            return []
        usd = sum((e.amount_usd for e in rows), D(0))
        return [CurrencyTotal("USD", usd, usd, len(rows))]

    async def first_movement_at(self, user_id: UUID) -> datetime | None:
        return min((e.occurred_at for e in self.expenses), default=None)

    async def account_balances(self, user_id: UUID) -> list[AccountBalance]:
        return []

    async def list_transactions(
        self,
        user_id: UUID,
        start: datetime,
        end: datetime,
        kind: TransactionKind | None,
        currency: Currency | None,
        category: str | None,
        limit: int,
    ) -> list[TransactionRow]:
        return []


class MemoryBudgets:
    def __init__(self) -> None:
        self.rows: list[tuple[Budget, UUID, bool]] = []  # (tope, categoría, vigente)

    async def active(self, user_id: UUID) -> list[Budget]:
        return sorted((b for b, _, on in self.rows if on), key=lambda b: b.category)

    async def set(
        self, user_id: UUID, category: Category, limit_usd: Decimal, raw_text: str | None
    ) -> tuple[Budget, Budget | None]:
        previous = None
        for i, (b, cat, on) in enumerate(self.rows):
            if on and cat == category.id:
                previous = b
                self.rows[i] = (b, cat, False)
        budget = Budget(uuid4(), category.name, limit_usd)
        self.rows.append((budget, category.id, True))
        return budget, previous

    async def remove(self, user_id: UUID, category: Category) -> Budget | None:
        for i, (b, cat, on) in enumerate(self.rows):
            if on and cat == category.id:
                self.rows[i] = (b, cat, False)
                return b
        return None

    async def undo(self, user_id: UUID, budget_id: UUID) -> bool:
        return False


def rates(*items: Rate) -> RateService:
    unused = RuntimeError("no se refresca en estas pruebas")
    sources = FakeRateSources(dolarapi=unused, p2p=unused, cop=unused, usdt=unused)
    return RateService(FakeRateStore(*items), sources, timedelta(hours=6), clock=lambda: NOW)


def rate(currency: QuotedCurrency, source: RateSource, usd: str) -> Rate:
    return Rate(currency, source, D(usd), NOW - timedelta(hours=1))


def budget_service(
    reports: MemoryReports, store: MemoryBudgets | None = None
) -> tuple[BudgetService, MemoryBudgets]:
    store = store or MemoryBudgets()
    svc = BudgetService(
        store,
        reports,
        FakeTransactionStore(),
        rates(rate("VES", "parallel", "0.002")),
        clock=lambda: NOW,
    )
    return svc, store


THIS_MONTH = datetime(2026, 11, 3, 16, tzinfo=UTC)


# ---- Topes ----


async def test_fijar_un_tope_en_dolares_muestra_lo_gastado_del_mes() -> None:
    reports = MemoryReports(
        Expense(THIS_MONTH, "comida", D(30)),
        Expense(NOW - timedelta(hours=1), "comida", D(50)),
        Expense(datetime(2026, 10, 20, tzinfo=UTC), "comida", D(99)),  # el mes pasado
        Expense(THIS_MONTH, "ocio", D(10)),
    )
    svc, store = budget_service(reports)
    outcome = await svc.apply(USER, BudgetDraft("comida", D(100), None), "tope comida 100")
    assert isinstance(outcome, BudgetSaved)
    assert outcome.progress.budget.limit_usd == D("100.00")
    assert outcome.progress.spent_usd == D(80)
    assert outcome.progress.state == "near"
    assert outcome.progress.days_left == 12
    assert outcome.converted_from is None and outcome.replaced is None
    assert [b.category for b in await store.active(USER.id)] == ["comida"]


async def test_un_tope_en_bolivares_se_guarda_en_dolares_con_la_tasa_del_usuario() -> None:
    svc, _ = budget_service(MemoryReports())
    outcome = await svc.apply(USER, BudgetDraft("ocio", D(20000), "VES"), "tope ocio 20 mil bs")
    assert isinstance(outcome, BudgetSaved)
    assert outcome.progress.budget.limit_usd == D("40.00")
    assert outcome.converted_from == (D(20000), "VES")
    assert outcome.rate is not None and outcome.rate.source == "parallel"


async def test_reemplazar_y_quitar_un_tope() -> None:
    svc, _ = budget_service(MemoryReports())
    await svc.apply(USER, BudgetDraft("comida", D(100), "USD"), "a")
    second = await svc.apply(USER, BudgetDraft("comida", D(120), "USD"), "b")
    assert isinstance(second, BudgetSaved) and second.replaced is not None
    assert second.replaced.limit_usd == D("100.00")

    removed = await svc.apply(USER, BudgetDraft("comida", None, None, remove=True), "quita")
    assert isinstance(removed, BudgetRemoved)
    again = await svc.apply(USER, BudgetDraft("comida", None, None, remove=True), "quita")
    assert again == NoBudget("comida")


async def test_categoria_desconocida_o_de_deudas_no_lleva_tope() -> None:
    svc, _ = budget_service(MemoryReports())
    unknown = await svc.apply(USER, BudgetDraft("mascotas", D(10), None), "x")
    assert isinstance(unknown, UnknownCategory)
    assert "pago de deudas" not in unknown.available and "comida" in unknown.available
    debt = await svc.apply(USER, BudgetDraft("pago de deudas", D(10), None), "x")
    assert isinstance(debt, UnknownCategory)
    assert await svc.apply(USER, BudgetDraft(None, D(10), None), "x") == Ask(
        "¿En qué categoría quieres el tope? Por ejemplo: «no quiero gastar más de 100 "
        "dólares al mes en comida»."
    )


async def test_sin_monto_pregunta_con_un_tope_sugerido_por_su_promedio() -> None:
    reports = MemoryReports(
        Expense(datetime(2026, 8, 10, tzinfo=UTC), "comida", D(62)),
        Expense(datetime(2026, 9, 10, tzinfo=UTC), "comida", D(80)),
        Expense(datetime(2026, 10, 10, tzinfo=UTC), "comida", D(71)),
    )
    svc, _ = budget_service(reports)
    outcome = await svc.apply(USER, BudgetDraft("comida", None, None), "quiero un tope en comida")
    assert outcome == Ask(
        "¿Cuánto quieres gastar como máximo al mes en comida? En los últimos meses gastaste "
        "unos 75,00 USD al mes en eso."
    )


async def test_sin_historial_pregunta_sin_sugerencia() -> None:
    svc, _ = budget_service(MemoryReports(Expense(THIS_MONTH, "comida", D(5))))
    outcome = await svc.apply(USER, BudgetDraft("comida", None, None), "x")
    assert outcome == Ask("¿Cuánto quieres gastar como máximo al mes en comida?")


async def test_estado_de_los_topes() -> None:
    reports = MemoryReports(Expense(THIS_MONTH, "ocio", D(50)))
    svc, _ = budget_service(reports)
    await svc.apply(USER, BudgetDraft("ocio", D(40), None), "x")
    await svc.apply(USER, BudgetDraft("comida", D(100), None), "x")
    status = await svc.status(USER)
    assert isinstance(status, BudgetStatus)
    assert [(p.budget.category, p.spent_usd, p.state) for p in status.rows] == [
        ("comida", D(0), "ok"),
        ("ocio", D(50), "over"),
    ]
    assert status.days_left == 12


# ---- Contexto al anotar ----


def saved_expense(category: str, kind: TransactionKind = "expense") -> SavedTransaction:
    return SavedTransaction(
        id=uuid4(),
        kind=kind,
        amount=D(15),
        currency="USD",
        category=category,
        description=category,
        account_name="efectivo USD",
        snapshot=UsdSnapshot(D(1), "pivot", D(15)),
        occurred_at=NOW,
    )


async def test_contexto_con_tope_y_sin_tope() -> None:
    monday = datetime(2026, 11, 16, 16, tzinfo=UTC)
    last_monday = datetime(2026, 11, 9, 16, tzinfo=UTC)
    reports = MemoryReports(
        Expense(datetime(2026, 10, 1, tzinfo=UTC), "otros", D(1)),  # anota desde octubre
        Expense(monday, "comida", D(62)),
        Expense(last_monday, "comida", D(50)),
        Expense(last_monday + timedelta(days=5), "comida", D(30)),  # después de "esta altura"
        Expense(monday, "ocio", D(20)),
    )
    budgets, _ = budget_service(reports)
    await budgets.apply(USER, BudgetDraft("ocio", D(40), None), "x")
    ctx = ContextService(budgets, reports, clock=lambda: NOW)

    lines = await ctx.lines(
        USER, [saved_expense("comida"), saved_expense("ocio"), saved_expense("salud")]
    )
    assert len(lines) == 2
    first, second = lines
    assert isinstance(first, BudgetLine) and first.progress.budget.category == "ocio"
    assert first.progress.spent_usd == D(20)
    assert second == WeekLine("comida", D(62), D(50))


async def test_sin_historial_de_la_semana_pasada_no_hay_comparacion() -> None:
    reports = MemoryReports(Expense(datetime(2026, 11, 12, tzinfo=UTC), "comida", D(5)))
    budgets, _ = budget_service(reports)
    ctx = ContextService(budgets, reports, clock=lambda: NOW)
    assert await ctx.lines(USER, [saved_expense("comida")]) == []


async def test_contexto_apagado_ingresos_y_deudas_no_llevan_linea() -> None:
    reports = MemoryReports(Expense(datetime(2026, 10, 1, tzinfo=UTC), "comida", D(5)))
    budgets, _ = budget_service(reports)
    ctx = ContextService(budgets, reports, clock=lambda: NOW)
    quiet = replace(USER, context_replies=False)
    assert await ctx.lines(quiet, [saved_expense("comida")]) == []
    assert await ctx.lines(USER, [saved_expense("salario", "income")]) == []
    assert await ctx.lines(USER, [saved_expense("pago de deudas")]) == []


class BrokenBudgets:
    async def progress(self, user: object) -> list[object]:
        raise RuntimeError("se cayó la base")


async def test_si_el_contexto_falla_no_hay_linea() -> None:
    ctx = ContextService(BrokenBudgets(), MemoryReports(), clock=lambda: NOW)  # type: ignore[arg-type]
    assert await ctx.lines(USER, [saved_expense("comida")]) == []


# ---- Colchón ----


async def test_colchon_con_saldo_y_gasto_de_los_ultimos_dias() -> None:
    reports = FakeReportStore(
        balances=[
            AccountBalance("efectivo USD", "USD", D(300)),
            AccountBalance("banesco", "VES", D(50000)),
        ],
        totals=[CurrencyTotal("USD", D(900), D(900), 30)],
        first_movement=datetime(2026, 1, 1, tzinfo=UTC),
    )
    queries = QueryService(reports, FakeTransactionStore(), rates(rate("VES", "parallel", "0.002")))
    answer = await queries.runway(USER, NOW.astimezone(USER_TZ))
    assert isinstance(answer, RunwayAnswer)
    # 300 + 50.000 × 0,002 = 400 USD; 900 / 90 días = 10 al día → 40 días.
    assert answer.result == Runway(D("400.000000"), D("10.00"), 40, 90)
    [call] = [args for name, args in reports.calls if name == "totals"]
    assert call["kind"] == "expense"
    assert call["end"] - call["start"] == timedelta(days=90)


async def test_colchon_sin_historial_suficiente() -> None:
    reports = FakeReportStore(first_movement=NOW - timedelta(days=3))
    queries = QueryService(reports, FakeTransactionStore(), rates())
    answer = await queries.runway(USER, NOW.astimezone(USER_TZ))
    assert answer.result == RunwayUnknown("short_history", 4)


# ---- Registro: topes por mensaje y contexto en la confirmación ----


def transaction_service(
    extraction: dict[str, object], reports: MemoryReports
) -> TransactionService:
    store = FakeTransactionStore()
    rate_service = rates(rate("VES", "parallel", "0.002"))
    budgets, _ = budget_service(reports)
    return TransactionService(
        store,
        FakeExtractor(Extraction.model_validate(extraction)),
        rate_service,
        ExchangeService(FakeExchangeStore(), store, rate_service),
        QueryService(FakeReportStore(), store, rate_service),
        CorrectionService(FakeCorrectionStore(), store, rate_service),
        DebtService(FakeDebtStore(), store, rate_service, clock=lambda: NOW),
        clock=lambda: NOW,
        budgets=budgets,
        context=ContextService(budgets, reports, clock=lambda: NOW),
    )


async def test_un_mensaje_de_tope_lo_fija() -> None:
    svc = transaction_service(
        {
            "intent": "set_budget",
            "confidence": 0.9,
            "budget": {"category": "Comida", "amount": 100, "currency": "USD"},
        },
        MemoryReports(),
    )
    outcome = await svc.register_text(USER, "no quiero gastar más de 100 dólares en comida")
    assert isinstance(outcome, BudgetSaved)
    assert outcome.progress.budget.category == "comida"


async def test_preguntar_por_los_topes() -> None:
    svc = transaction_service(
        {"intent": "query", "confidence": 0.9, "query": {"tool": "budget_status"}},
        MemoryReports(),
    )
    assert await svc.register_text(USER, "¿cómo voy con mis topes?") == BudgetStatus([], 12)


async def test_el_gasto_anotado_trae_su_contexto() -> None:
    reports = MemoryReports(
        Expense(datetime(2026, 10, 1, tzinfo=UTC), "otros", D(1)),
        Expense(datetime(2026, 11, 17, tzinfo=UTC), "comida", D(10)),
    )
    svc = transaction_service(
        {
            "intent": "log_transactions",
            "confidence": 0.9,
            "transactions": [
                {
                    "kind": "expense",
                    "amount": 15,
                    "currency": "USD",
                    "currency_confidence": 0.9,
                    "category": "comida",
                    "description": "almuerzo",
                }
            ],
        },
        reports,
    )
    outcome = await svc.register_text(USER, "almuerzo 15 dólares")
    assert isinstance(outcome, Saved)
    assert outcome.context == [WeekLine("comida", D(10), D(0))]
