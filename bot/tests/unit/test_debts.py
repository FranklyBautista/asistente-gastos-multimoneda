"""Deudas (Fase 11): dominio, servicio con dobles en memoria y textos del chat."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest

from gastos.chat.handlers.debts import debt_line, debt_list_text, no_match_text, payment_text
from gastos.domain.conversion import Rate
from gastos.domain.debt import (
    Debt,
    DebtDraft,
    PaymentDraft,
    clean_counterparty,
    counterparty_key,
    matching_debts,
)
from gastos.domain.errors import DebtChanged
from gastos.extraction.schema import Extraction
from gastos.services.corrections import CorrectionService
from gastos.services.debts import (
    ChooseAccount,
    ChooseDebt,
    DebtList,
    DebtSaved,
    DebtService,
    NeedsDebtCurrency,
    NoMatchingDebt,
    PaymentSaved,
)
from gastos.services.exchanges import ExchangeService
from gastos.services.outcomes import Ask
from gastos.services.query_tools import QueryService
from gastos.services.rates import RateService
from gastos.services.transactions import TransactionService
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

NOW = datetime(2026, 11, 15, 19, tzinfo=UTC)
USER = make_user(onboarded=True)  # Caracas, Bs con tasa paralela
TZ_DAY = datetime(2026, 11, 10, 12, tzinfo=UTC)


def rates() -> RateService:
    unused = RuntimeError("no se refresca en estas pruebas")
    sources = FakeRateSources(dolarapi=unused, p2p=unused, cop=unused, usdt=unused)
    store = FakeRateStore(
        Rate("VES", "parallel", Decimal("0.001"), NOW),
        Rate("COP", "fx", Decimal("0.00025"), NOW - timedelta(hours=10)),
        Rate("USDT", "coingecko", Decimal("0.999"), NOW),
    )
    return RateService(store, sources, timedelta(hours=6), clock=lambda: NOW)


def debt(
    counterparty: str = "Miguel",
    amount: str = "20",
    currency: Any = "USD",
    direction: Any = "i_owe",
    **fields: Any,
) -> Debt:
    base: dict[str, Any] = {
        "id": uuid4(),
        "direction": direction,
        "counterparty": counterparty,
        "currency": currency,
        "amount": Decimal(amount),
        "remaining": Decimal(amount),
        "status": "open",
        "description": None,
        "category": None,
        "incurred_at": TZ_DAY,
    }
    return Debt(**(base | fields))


def setup(*debts: Debt) -> tuple[DebtService, FakeDebtStore, FakeTransactionStore]:
    store, accounts = FakeDebtStore(*debts), FakeTransactionStore()
    return DebtService(store, accounts, rates(), clock=lambda: NOW), store, accounts


def payment(counterparty: str = "miguel", amount: str | None = None, **fields: Any) -> PaymentDraft:
    base: dict[str, Any] = {
        "direction": "i_owe",
        "counterparty": counterparty,
        "amount": None if amount is None else Decimal(amount),
        "currency": None,
    }
    return PaymentDraft(**(base | fields))


# ---- Dominio ----


@pytest.mark.parametrize(
    ("name", "key"),
    [
        ("Miguel", "miguel"),
        ("  Míguel   Ángel ", "miguel angel"),
        ("NÚÑEZ", "nunez"),
    ],
)
def test_la_clave_de_la_contraparte_coincide_con_la_de_la_base(name: str, key: str) -> None:
    assert counterparty_key(name) == key


def test_el_nombre_se_limpia_para_mostrarlo() -> None:
    assert clean_counterparty("  miguel   ángel ") == "Miguel ángel"


def test_una_deuda_necesita_contraparte_y_monto_positivo() -> None:
    with pytest.raises(ValueError, match="contraparte"):
        DebtDraft("i_owe", "  ", Decimal(1), "USD", 0.9)
    with pytest.raises(ValueError, match="positivo"):
        DebtDraft("i_owe", "Ana", Decimal(0), "USD", 0.9)


def test_busca_por_persona_direccion_y_moneda() -> None:
    miguel_angel = debt("Miguel Ángel")
    luisa = debt("Luisa")
    me_debe = debt("Miguel", direction="owed_to_me")
    en_bs = debt("Miguel", currency="VES")
    pagada = debt("Miguel", status="settled", remaining=Decimal(0))
    found = matching_debts([miguel_angel, luisa, me_debe, en_bs, pagada], payment("miguel"))
    assert found == [miguel_angel, en_bs]
    only_usd = matching_debts([miguel_angel, en_bs], payment("miguel", currency="USD"))
    assert only_usd == [miguel_angel]
    assert matching_debts([miguel_angel], payment("migue")) == []  # sin adivinar prefijos


# ---- Anotar ----


async def test_deuda_en_usd_se_guarda_con_el_pivote() -> None:
    svc, store, _ = setup()
    draft = DebtDraft("i_owe", "Miguel", Decimal(20), "USD", 0.9, category="comida")
    outcome = await svc.register(USER, draft, "le debo 20 dólares a miguel")
    assert isinstance(outcome, DebtSaved)
    [item] = store.inserted
    assert (item.amount, item.currency, item.snapshot.rate_source) == (Decimal(20), "USD", "pivot")
    assert item.category is not None and item.category.name == "comida"
    assert outcome.stale_rate is None


async def test_moneda_dudosa_se_pregunta_y_luego_guarda_con_su_tasa() -> None:
    svc, store, _ = setup()
    draft = DebtDraft("owed_to_me", "Luisa", Decimal(50000), None, 0)
    outcome = await svc.register(USER, draft, "luisa me debe 50 mil")
    assert isinstance(outcome, NeedsDebtCurrency)
    assert store.inserted == []
    saved = await svc.choose_currency(USER, outcome.token, "COP")
    assert isinstance(saved, DebtSaved)
    assert store.inserted[0].snapshot.amount_usd == Decimal("12.500000")
    assert saved.stale_rate is not None  # la tasa de COP tiene 10 h
    assert await svc.choose_currency(USER, outcome.token, "COP") is None  # un solo uso


async def test_el_pendiente_de_otro_usuario_no_sirve() -> None:
    svc, _, _ = setup()
    draft = DebtDraft("i_owe", "Miguel", Decimal(5), None, 0)
    outcome = await svc.register(USER, draft, "le debo 5 a miguel")
    assert isinstance(outcome, NeedsDebtCurrency)
    assert await svc.choose_currency(make_user(222, onboarded=True), outcome.token, "USD") is None


# ---- Pagar ----


async def test_una_deuda_sin_monto_se_paga_completa_y_pregunta_la_cuenta() -> None:
    miguel = debt()
    svc, store, accounts = setup(miguel)
    outcome = await svc.settle(USER, payment(), "le pagué a miguel")
    assert isinstance(outcome, ChooseAccount)
    assert outcome.amount == Decimal(20)
    assert [a.name for a in outcome.accounts] == ["efectivo USD"]

    usd = accounts.account_list[3]
    saved = await svc.choose_account(USER, outcome.token, 0)
    assert isinstance(saved, PaymentSaved)
    assert saved.debt.status == "settled"
    assert saved.movement is not None
    assert (saved.movement.kind, saved.movement.category) == ("expense", "pago de deudas")
    assert saved.movement.account_name == usd.name
    assert await svc.choose_account(USER, outcome.token, 0) is None  # un solo uso
    assert len(store.payments) == 1


async def test_sin_movimiento_no_crea_gasto() -> None:
    svc, _, _ = setup(debt())
    outcome = await svc.settle(USER, payment(amount="5"), "le pagué 5 a miguel")
    assert isinstance(outcome, ChooseAccount)
    saved = await svc.choose_account(USER, outcome.token, None)
    assert isinstance(saved, PaymentSaved)
    assert saved.movement is None
    assert (saved.debt.status, saved.debt.remaining) == ("partial", Decimal(15))


async def test_cobrar_una_deuda_crea_un_ingreso() -> None:
    svc, _, _ = setup(debt("Luisa", "50000", "COP", "owed_to_me"))
    p = payment("luisa", direction="owed_to_me")
    outcome = await svc.settle(USER, p, "luisa me pagó")
    assert isinstance(outcome, ChooseAccount)
    saved = await svc.choose_account(USER, outcome.token, 0)
    assert isinstance(saved, PaymentSaved) and saved.movement is not None
    assert (saved.movement.kind, saved.movement.category) == ("income", "cobro de deudas")
    assert saved.movement.snapshot.rate_source == "fx"


async def test_la_cuenta_mencionada_se_usa_sin_preguntar() -> None:
    svc, _, _ = setup(debt("Miguel", "20", "VES"))
    outcome = await svc.settle(USER, payment(account_hint="banesco"), "le pagué por banesco")
    assert isinstance(outcome, PaymentSaved)
    assert outcome.movement is not None and outcome.movement.account_name == "banesco"


async def test_una_pista_que_no_coincide_igual_pregunta() -> None:
    svc, _, _ = setup(debt("Miguel", "20", "VES"))
    outcome = await svc.settle(USER, payment(account_hint="zelle"), "le pagué por zelle")
    assert isinstance(outcome, ChooseAccount)


async def test_varias_deudas_con_la_persona_piden_elegir() -> None:
    a, b = debt(description="almuerzo"), debt(amount="50", description="préstamo")
    svc, _, _ = setup(a, b)
    outcome = await svc.settle(USER, payment(), "le pagué a miguel")
    assert isinstance(outcome, ChooseDebt)
    assert outcome.candidates == [a, b]
    chosen = await svc.choose_debt(USER, outcome.token, 1)
    assert isinstance(chosen, ChooseAccount)
    assert (chosen.debt.id, chosen.amount) == (b.id, Decimal(50))
    assert await svc.choose_debt(USER, outcome.token, 0) is None  # un solo uso


async def test_el_monto_descarta_las_deudas_donde_no_cabe() -> None:
    small, big = debt(amount="5"), debt(amount="50")
    svc, _, _ = setup(small, big)
    outcome = await svc.settle(USER, payment(amount="20"), "le pagué 20 a miguel")
    assert isinstance(outcome, ChooseAccount)
    assert outcome.debt.id == big.id


async def test_un_pago_mayor_a_lo_pendiente_se_pregunta() -> None:
    svc, store, _ = setup(debt())
    outcome = await svc.settle(USER, payment(amount="25"), "le pagué 25 a miguel")
    assert isinstance(outcome, Ask)
    assert "20,00 USD" in outcome.question
    assert store.payments == {}


async def test_sin_deuda_que_cuadre_muestra_las_pendientes() -> None:
    luisa = debt("Luisa")
    svc, _, _ = setup(luisa)
    outcome = await svc.settle(USER, payment(), "le pagué a miguel")
    assert isinstance(outcome, NoMatchingDebt)
    assert outcome.open_debts == [luisa]


async def test_si_otro_pago_llega_antes_no_se_guarda_nada() -> None:
    svc, store, _ = setup(debt())
    first = await svc.settle(USER, payment(), "le pagué a miguel")
    second = await svc.settle(USER, payment(), "le pagué a miguel")
    assert isinstance(first, ChooseAccount) and isinstance(second, ChooseAccount)
    await svc.choose_account(USER, first.token, None)
    with pytest.raises(DebtChanged):
        await svc.choose_account(USER, second.token, None)
    assert len(store.payments) == 1


async def test_deshacer_una_deuda_con_pagos_no_se_permite() -> None:
    miguel = debt()
    svc, _, _ = setup(miguel)
    outcome = await svc.settle(USER, payment(amount="5"), "le pagué 5 a miguel")
    assert isinstance(outcome, ChooseAccount)
    saved = await svc.choose_account(USER, outcome.token, None)
    assert isinstance(saved, PaymentSaved)
    assert await svc.undo_debt(USER, miguel.id) == 0
    assert await svc.undo_payment(USER, saved.payment_id) == 1
    assert await svc.undo_payment(USER, saved.payment_id) == 0
    assert await svc.undo_debt(USER, miguel.id) == 1


async def test_listar_filtra_por_persona() -> None:
    svc, _, _ = setup(debt("Miguel Ángel"), debt("Luisa"))
    answer = await svc.list(USER, counterparty="miguel")
    assert [d.counterparty for d in answer.debts] == ["Miguel Ángel"]


# ---- Desde el texto ----


def transactions(
    extraction: dict[str, Any], *debts: Debt
) -> tuple[TransactionService, FakeExtractor]:
    tx_store, rate_service = FakeTransactionStore(), rates()
    extractor = FakeExtractor(Extraction.model_validate(extraction))
    svc = TransactionService(
        tx_store,
        extractor,
        rate_service,
        ExchangeService(FakeExchangeStore(), tx_store, rate_service),
        QueryService(FakeReportStore(), tx_store, rate_service),
        CorrectionService(FakeCorrectionStore(), tx_store, rate_service),
        DebtService(FakeDebtStore(*debts), tx_store, rate_service, clock=lambda: NOW),
        clock=lambda: NOW,
    )
    return svc, extractor


async def test_log_debt_desde_el_texto() -> None:
    svc, _ = transactions(
        {
            "intent": "log_debt",
            "confidence": 0.9,
            "debt": {
                "direction": "i_owe",
                "counterparty": "  miguel ",
                "amount": 20,
                "currency": "USD",
                "currency_confidence": 0.9,
                "category": "pago de deudas",  # no se ofrece al LLM: se descarta
                "description": "almuerzo",
            },
        }
    )
    outcome = await svc.register_text(USER, "le debo 20 dólares a miguel")
    assert isinstance(outcome, DebtSaved)
    assert (outcome.debt.counterparty, outcome.debt.category) == ("Miguel", None)


async def test_settle_debt_y_pregunta_de_monto_se_encadenan() -> None:
    svc, extractor = transactions(
        {
            "intent": "settle_debt",
            "confidence": 0.9,
            "debt_payment": {"direction": "i_owe", "counterparty": "miguel", "amount": 30},
        },
        debt(),
    )
    outcome = await svc.register_text(USER, "le pagué 30 a miguel")
    assert isinstance(outcome, Ask)
    await svc.register_text(USER, "fueron 20")
    assert extractor.calls[1][1] == ("le pagué 30 a miguel", outcome.question)


async def test_la_consulta_de_deudas_va_al_servicio_de_deudas() -> None:
    svc, _ = transactions(
        {
            "intent": "query",
            "confidence": 0.9,
            "query": {"tool": "list_debts", "direction": "i_owe"},
        },
        debt(),
        debt("Luisa", direction="owed_to_me"),
    )
    outcome = await svc.register_text(USER, "¿cuánto debo?")
    assert isinstance(outcome, DebtList)
    assert [d.counterparty for d in outcome.debts] == ["Miguel"]


async def test_el_llm_no_ve_las_categorias_de_deudas() -> None:
    seen: list[Any] = []

    class Spy(FakeExtractor):
        async def extract(self, text: str, categories: Any, *args: Any, **kw: Any) -> Extraction:
            seen.append(categories)
            return await super().extract(text, categories, *args, **kw)

    tx_store, rate_service = FakeTransactionStore(), rates()
    svc = TransactionService(
        tx_store,
        Spy(Extraction.model_validate({"intent": "other", "confidence": 0.9})),
        rate_service,
        ExchangeService(FakeExchangeStore(), tx_store, rate_service),
        QueryService(FakeReportStore(), tx_store, rate_service),
        CorrectionService(FakeCorrectionStore(), tx_store, rate_service),
        DebtService(FakeDebtStore(), tx_store, rate_service),
    )
    await svc.register_text(USER, "hola")
    assert "pago de deudas" not in seen[0].expense
    assert "cobro de deudas" not in seen[0].income


# ---- Textos del chat ----


def test_la_liquidada_sale_tachada_y_los_nombres_se_escapan() -> None:
    from zoneinfo import ZoneInfo

    settled = debt("<b>Ana</b>", status="settled", remaining=Decimal(0))
    line = debt_line(settled, ZoneInfo("America/Caracas"))
    assert line.startswith("<s>Le debes 20,00 USD a &lt;b&gt;Ana&lt;/b&gt;")
    assert line.endswith("</s> ✔️")


def test_la_parcial_muestra_lo_pendiente() -> None:
    from zoneinfo import ZoneInfo

    partial = debt(
        status="partial", remaining=Decimal(5), description="almuerzo", category="comida"
    )
    line = debt_line(partial, ZoneInfo("America/Caracas"))
    assert "comida · almuerzo" in line
    assert "(pendiente 5,00 USD)" in line


def test_la_lista_agrupa_y_suma_por_moneda() -> None:
    answer = DebtList(
        [
            debt(),
            debt("Pedro", amount="5"),
            debt("Luisa", "50000", "COP", "owed_to_me"),
        ],
        None,
    )
    text = debt_list_text(answer, USER)
    assert "<b>Debes</b> (total pendiente: 25,00 USD)" in text
    assert "<b>Te deben</b> (total pendiente: 50.000 COP)" in text


def test_sin_deudas() -> None:
    assert "No le debes nada" in debt_list_text(DebtList([], "i_owe"), USER)


def test_sin_coincidencia_de_cobro_sugiere_ingreso() -> None:
    p = payment("luisa", direction="owed_to_me")
    assert "ingreso" in no_match_text(NoMatchingDebt(p, []), USER)


def test_pago_sin_movimiento_lo_dice() -> None:
    after = debt(status="partial", remaining=Decimal(15))
    text = payment_text(PaymentSaved(uuid4(), Decimal(5), after, None), USER)
    assert "Le pagaste 5,00 USD a Miguel; queda pendiente 15,00 USD." in text
    assert "Sin movimiento" in text


# ---- Resumen semanal ----


def test_el_resumen_suma_lo_pendiente_por_moneda() -> None:
    from gastos.services.weekly_summary import debts_section

    section = debts_section(
        [
            debt(status="partial", remaining=Decimal(15)),
            debt("Pedro", amount="5"),
            debt("Luisa", "50000", "COP", "owed_to_me"),
            debt("Ana", status="settled", remaining=Decimal(0)),
        ]
    )
    assert section == (
        "📒 Deudas pendientes: debes 20,00 USD; te deben 50.000 COP. Detalle en /deudas."
    )
    assert debts_section([]) is None
