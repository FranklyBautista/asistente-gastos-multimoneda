"""Registro desde texto libre con LLM, tasas y base de datos falsos."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest

from gastos.domain.account import pick_account
from gastos.domain.conversion import Rate
from gastos.domain.currency import QuotedCurrency, RateSource
from gastos.domain.errors import AccountNotFound, RateUnavailable
from gastos.extraction.schema import Extraction
from gastos.services.rates import RateService
from gastos.services.transactions import (
    Ask,
    NeedsCurrency,
    NotATransaction,
    Saved,
    TransactionService,
)
from tests.fakes import (
    FakeExtractor,
    FakeRateSources,
    FakeRateStore,
    FakeTransactionStore,
    make_accounts,
    make_user,
)

NOW = datetime(2026, 10, 31, 19, tzinfo=UTC)
USER = make_user(onboarded=True)  # Caracas, Bs con tasa paralela


def rate(currency: QuotedCurrency, source: RateSource, usd: str, age_h: int = 0) -> Rate:
    return Rate(currency, source, Decimal(usd), NOW - timedelta(hours=age_h))


def rate_service(*rates: Rate) -> RateService:
    unused = RuntimeError("no se refresca en estas pruebas")
    sources = FakeRateSources(dolarapi=unused, p2p=unused, cop=unused, usdt=unused)
    return RateService(FakeRateStore(*rates), sources, timedelta(hours=6), clock=lambda: NOW)


RATES = (
    rate("VES", "parallel", "0.001"),
    rate("VES", "bcv", "0.002"),
    rate("COP", "fx", "0.00025"),
    rate("USDT", "coingecko", "0.999"),
)


def tx(**fields: Any) -> dict[str, Any]:
    base = {"kind": "expense", "currency_confidence": 0.95, "description": "algo"}
    return base | fields


def service(
    *transactions: dict[str, Any], rates: RateService | None = None, **extraction: Any
) -> tuple[TransactionService, FakeTransactionStore]:
    data = {"intent": "log_transactions", "confidence": 0.9, "transactions": list(transactions)}
    store = FakeTransactionStore()
    extractor = FakeExtractor(Extraction.model_validate(data | extraction))
    svc = TransactionService(store, extractor, rates or rate_service(*RATES), clock=lambda: NOW)
    return svc, store


async def test_gasto_en_bs_se_guarda_con_la_tasa_de_su_fuente() -> None:
    svc, store = service(tx(amount=70, currency="VES", category="transporte", description="pasaje"))
    outcome = await svc.register_text(USER, "pagué 70 bs de pasaje")
    assert isinstance(outcome, Saved)
    [item] = store.batches[0]
    assert (item.amount, item.currency, item.category.name) == (Decimal(70), "VES", "transporte")
    assert item.account.name == "banesco"  # primera cuenta en Bs por nombre
    assert (item.snapshot.usd_per_unit, item.snapshot.rate_source) == (Decimal("0.001"), "parallel")
    assert item.snapshot.amount_usd == Decimal("0.070000")
    assert item.raw_text == "pagué 70 bs de pasaje"
    assert outcome.stale_rates == []


async def test_usd_es_el_pivote_y_no_pide_tasa() -> None:
    svc, store = service(tx(amount=12.5, currency="USD"), rates=rate_service())
    assert isinstance(await svc.register_text(USER, "12.5 dólares"), Saved)
    snapshot = store.batches[0][0].snapshot
    assert (snapshot.usd_per_unit, snapshot.rate_source, snapshot.amount_usd) == (
        Decimal(1),
        "pivot",
        Decimal("12.5"),
    )


async def test_varios_movimientos_se_guardan_juntos() -> None:
    svc, store = service(
        tx(amount=15, currency="USD", category="comida", description="almuerzo"),
        tx(amount=3, currency="USD", category="comida", description="café"),
        tx(kind="income", amount=200, currency="USDT", description="pago"),
    )
    outcome = await svc.register_text(USER, "almuerzo 15 y café 3 dólares, me pagaron 200 usdt")
    assert isinstance(outcome, Saved)
    assert len(store.batches) == 1
    assert [t.description for t in outcome.transactions] == ["almuerzo", "café", "pago"]
    # Sin categoría reconocida, el ingreso va a la de respaldo de su tipo.
    assert store.batches[0][2].category.name == "otros ingresos"


async def test_moneda_dudosa_espera_los_botones_y_luego_guarda() -> None:
    svc, store = service(
        tx(amount=20000, currency=None, currency_confidence=0, description="taxi"),
        tx(amount=70, currency="VES", description="pasaje"),
    )
    outcome = await svc.register_text(USER, "taxi 20 mil y pasaje 70 bs")
    assert isinstance(outcome, NeedsCurrency)
    assert store.batches == []  # nada se guarda antes de responder

    saved = await svc.choose_currency(USER, outcome.token, "COP")
    assert isinstance(saved, Saved)
    assert [(t.currency, t.amount) for t in store.batches[0]] == [
        ("COP", Decimal(20000)),
        ("VES", Decimal(70)),  # la moneda elegida solo cambia los dudosos
    ]
    assert store.batches[0][0].snapshot.amount_usd == Decimal("5.000000")
    # El token es de un solo uso.
    assert await svc.choose_currency(USER, outcome.token, "COP") is None


async def test_confianza_baja_tambien_se_pregunta() -> None:
    svc, _ = service(tx(amount=15, currency="COP", currency_confidence=0.6))
    assert isinstance(await svc.register_text(USER, "15 lucas"), NeedsCurrency)


async def test_el_pendiente_de_otro_usuario_no_se_puede_usar() -> None:
    svc, store = service(tx(amount=15, currency=None, currency_confidence=0))
    outcome = await svc.register_text(USER, "15")
    assert isinstance(outcome, NeedsCurrency)
    assert await svc.choose_currency(make_user(222), outcome.token, "USD") is None
    assert store.batches == []


async def test_el_pendiente_expira() -> None:
    clock = [NOW]
    store = FakeTransactionStore()
    extractor = FakeExtractor(
        Extraction.model_validate(
            {
                "intent": "log_transactions",
                "confidence": 0.9,
                "transactions": [tx(amount=15, currency=None, currency_confidence=0)],
            }
        )
    )
    svc = TransactionService(store, extractor, rate_service(*RATES), clock=lambda: clock[0])
    outcome = await svc.register_text(USER, "15")
    assert isinstance(outcome, NeedsCurrency)
    clock[0] = NOW + timedelta(hours=1)
    assert await svc.choose_currency(USER, outcome.token, "USD") is None


async def test_tasa_vieja_se_guarda_pero_se_avisa() -> None:
    svc, _ = service(
        tx(amount=70, currency="VES"), rates=rate_service(rate("VES", "parallel", "0.001", 8))
    )
    outcome = await svc.register_text(USER, "70 bs")
    assert isinstance(outcome, Saved)
    assert [r.currency for r in outcome.stale_rates] == ["VES"]


async def test_sin_tasa_no_se_guarda_nada() -> None:
    svc, store = service(tx(amount=70, currency="VES"), rates=rate_service())
    with pytest.raises(RateUnavailable):
        await svc.register_text(USER, "70 bs")
    assert store.batches == []


async def test_respeta_la_fuente_de_bs_del_usuario() -> None:
    svc, store = service(tx(amount=10, currency="VES"))
    await svc.register_text(replace(USER, ves_rate_source="bcv"), "10 bs")
    assert store.batches[0][0].snapshot.rate_source == "bcv"


@pytest.mark.parametrize("intent", ["log_exchange", "query", "correction", "other"])
async def test_otras_intenciones_no_guardan(intent: str) -> None:
    svc, store = service(intent=intent)
    assert await svc.register_text(USER, "...") == NotATransaction(intent)  # type: ignore[arg-type]
    assert store.batches == []


async def test_aclaracion_de_monto_se_pregunta_en_texto() -> None:
    question = "¿Cuánto gastaste en el almuerzo?"
    svc, store = service(clarification={"field": "amount", "question": question})
    assert await svc.register_text(USER, "gasté en el almuerzo") == Ask(question)
    assert store.batches == []


async def test_sin_movimientos_ni_aclaracion_pide_el_monto() -> None:
    svc, _ = service()
    assert isinstance(await svc.register_text(USER, "gasté"), Ask)


async def test_deshacer_borra_todo_el_mensaje() -> None:
    svc, store = service(tx(amount=1, currency="USD"), tx(amount=2, currency="USD"))
    outcome = await svc.register_text(USER, "1 y 2 dólares")
    assert isinstance(outcome, Saved)
    assert await svc.undo(USER, outcome.transactions[0].id) == 2
    assert await svc.undo(USER, outcome.transactions[0].id) == 0


async def test_cuenta_mencionada_se_respeta() -> None:
    svc, store = service(tx(amount=10, currency="VES", account_hint="efectivo"))
    await svc.register_text(USER, "10 bs en efectivo")
    assert store.batches[0][0].account.name == "efectivo Bs"


async def test_sin_cuenta_en_la_moneda_avisa() -> None:
    svc, store = service(tx(amount=10, currency="COP"))
    store.account_list = [a for a in store.account_list if a.currency != "COP"]
    with pytest.raises(AccountNotFound):
        await svc.register_text(USER, "10 pesos")


def test_pick_account_con_pista_desconocida_usa_la_primera() -> None:
    accounts = make_accounts()
    assert pick_account(accounts, "VES", "mercantil") == accounts[0]
    assert pick_account(accounts, "VES", "Efectivo") == accounts[1]
    assert pick_account(accounts, "USDT", None) == accounts[4]
