"""Cambios entre monedas de punta a punta con LLM, tasas y base de datos falsos."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest

from gastos.domain.conversion import Rate
from gastos.domain.currency import QuotedCurrency, RateSource
from gastos.domain.errors import AccountNotFound
from gastos.extraction.schema import Extraction
from gastos.services.exchanges import ExchangeSaved, ExchangeService
from gastos.services.outcomes import Ask, NotATransaction
from gastos.services.rates import RateService
from gastos.services.transactions import Saved, TransactionService
from tests.fakes import (
    FakeExchangeStore,
    FakeExtractor,
    FakeRateSources,
    FakeRateStore,
    FakeTransactionStore,
    make_user,
)

NOW = datetime(2026, 10, 31, 19, tzinfo=UTC)
USER = make_user(onboarded=True)  # Bs con tasa paralela
D = Decimal


def rate(currency: QuotedCurrency, source: RateSource, usd: str, age_h: int = 0) -> Rate:
    return Rate(currency, source, D(usd), NOW - timedelta(hours=age_h))


RATES = (
    rate("VES", "parallel", "0.001"),  # 1.000 Bs por USD
    rate("COP", "fx", "0.00025"),  # 4.000 COP por USD
    rate("USDT", "coingecko", "0.999"),
)


def exchange(**fields: Any) -> Extraction:
    data = {"from_currency": "USDT", "to_currency": "VES"} | fields
    return Extraction.model_validate(
        {"intent": "log_exchange", "confidence": 0.95, "exchange": data}
    )


class Setup:
    def __init__(self, *extractions: Extraction, rates: tuple[Rate, ...] = RATES) -> None:
        unused = RuntimeError("no se refresca en estas pruebas")
        sources = FakeRateSources(dolarapi=unused, p2p=unused, cop=unused, usdt=unused)
        rate_service = RateService(
            FakeRateStore(*rates), sources, timedelta(hours=6), clock=lambda: NOW
        )
        self.store = FakeTransactionStore()
        self.exchanges = FakeExchangeStore()
        self.extractor = FakeExtractor(*extractions)
        self.clock = [NOW]
        self.service = TransactionService(
            self.store,
            self.extractor,
            rate_service,
            ExchangeService(self.exchanges, self.store, rate_service),
            clock=lambda: self.clock[0],
        )


async def test_venta_de_usdt_con_tasa_se_guarda_y_se_compara() -> None:
    s = Setup(exchange(from_amount=50, rate=985))
    outcome = await s.service.register_text(USER, "cambié 50 usdt a bs a 985")
    assert isinstance(outcome, ExchangeSaved)
    [item] = s.exchanges.saved
    assert (item.from_account.name, item.to_account.name) == ("wallet USDT", "banesco")
    assert item.amounts.to_amount == D("49250.000000")
    assert item.amounts.effective_rate == D("985.0000000000")
    assert item.reference_rate == D("999.0000000000")  # 0,999 / 0,001
    assert item.raw_text == "cambié 50 usdt a bs a 985"
    assert outcome.difference_pct == D("-1.40")
    assert [c.rate.source for c in outcome.reference_rates] == ["coingecko", "parallel"]


async def test_compra_de_usdt_con_la_tasa_al_reves() -> None:
    s = Setup(exchange(from_currency="VES", to_currency="USDT", to_amount=20, rate=990))
    outcome = await s.service.register_text(USER, "compré 20 usdt con bs a 990")
    assert isinstance(outcome, ExchangeSaved)
    amounts = s.exchanges.saved[0].amounts
    assert (amounts.from_amount, amounts.to_amount) == (D("19800.000000"), D(20))
    # Pagaste 990 Bs por USDT con una referencia de 999: recibiste un poco más.
    assert outcome.difference_pct is not None and outcome.difference_pct > 0


async def test_usd_es_el_pivote_de_la_referencia() -> None:
    s = Setup(exchange(from_currency="USD", to_currency="COP", from_amount=100, to_amount=390000))
    outcome = await s.service.register_text(USER, "vendí 100 dólares por 390 mil pesos")
    assert isinstance(outcome, ExchangeSaved)
    assert s.exchanges.saved[0].reference_rate == D("4000.0000000000")
    assert outcome.difference_pct == D("-2.50")
    assert [c.rate.source for c in outcome.reference_rates] == ["fx"]


async def test_cuentas_mencionadas_se_respetan() -> None:
    s = Setup(
        exchange(
            from_currency="USD",
            from_amount=100,
            to_amount=98500,
            from_account_hint="efectivo",
            to_account_hint="efectivo",
        )
    )
    await s.service.register_text(USER, "...")
    item = s.exchanges.saved[0]
    assert (item.from_account.name, item.to_account.name) == ("efectivo USD", "efectivo Bs")


async def test_sin_tasas_guardadas_se_guarda_sin_referencia() -> None:
    s = Setup(exchange(from_amount=50, to_amount=49000), rates=())
    outcome = await s.service.register_text(USER, "...")
    assert isinstance(outcome, ExchangeSaved)
    assert outcome.difference_pct is None
    assert s.exchanges.saved[0].reference_rate is None


@pytest.mark.parametrize(
    ("fields", "question"),
    [
        ({"from_amount": 50}, "¿A qué tasa cambiaste o cuántos bolívares recibiste?"),
        ({"to_amount": 49000}, "¿Cuántos USDT entregaste o a qué tasa fue?"),
        ({"rate": 985}, "¿Cuántos USDT cambiaste?"),
        ({}, "¿Cuántos USDT cambiaste y a qué tasa?"),
        (
            {"from_currency": None, "to_amount": 20},
            "¿Qué moneda entregaste para recibir los bolívares?",
        ),
        ({"to_currency": None}, "¿Qué moneda recibiste por los USDT?"),
        (
            {"from_currency": None, "to_currency": None},
            "¿De qué moneda a qué moneda fue el cambio?",
        ),
    ],
)
async def test_si_falta_algo_hace_una_sola_pregunta(fields: dict[str, Any], question: str) -> None:
    s = Setup(exchange(**fields))
    assert await s.service.register_text(USER, "...") == Ask(question)
    assert s.exchanges.saved == []


async def test_misma_moneda_es_una_transferencia() -> None:
    s = Setup(exchange(from_currency="VES", to_currency="VES", from_amount=10, to_amount=10))
    assert await s.service.register_text(USER, "...") == NotATransaction("transfer")


async def test_sin_cuenta_en_la_moneda_avisa() -> None:
    s = Setup(exchange(from_amount=50, rate=985))
    s.store.account_list = [a for a in s.store.account_list if a.currency != "USDT"]
    with pytest.raises(AccountNotFound):
        await s.service.register_text(USER, "...")


async def test_la_respuesta_completa_el_cambio_pendiente() -> None:
    s = Setup(exchange(from_amount=50), exchange(from_amount=50, rate=985))
    question = await s.service.register_text(USER, "cambié 50 usdt a bs")
    assert isinstance(question, Ask)

    outcome = await s.service.register_text(USER, "a 985")
    assert isinstance(outcome, ExchangeSaved)
    assert s.extractor.calls[1] == ("a 985", ("cambié 50 usdt a bs", question.question))
    assert s.exchanges.saved[0].raw_text == "cambié 50 usdt a bs / a 985"
    # Una vez respondida, la pregunta no se vuelve a usar.
    await s.service.register_text(USER, "otra cosa")
    assert s.extractor.calls[2] == ("otra cosa", None)


async def test_la_pregunta_vence() -> None:
    s = Setup(exchange(from_amount=50))
    await s.service.register_text(USER, "cambié 50 usdt a bs")
    s.clock[0] = NOW + timedelta(minutes=11)
    await s.service.register_text(USER, "a 985")
    assert s.extractor.calls[1] == ("a 985", None)


async def test_la_pregunta_es_de_cada_usuario() -> None:
    s = Setup(exchange(from_amount=50))
    await s.service.register_text(USER, "cambié 50 usdt a bs")
    await s.service.register_text(make_user(222, onboarded=True), "a 985")
    assert s.extractor.calls[1] == ("a 985", None)


async def test_gasto_que_responde_a_una_pregunta_de_monto() -> None:
    ask = Extraction.model_validate(
        {
            "intent": "log_transactions",
            "confidence": 0.6,
            "clarification": {"field": "amount", "question": "¿Cuánto gastaste?"},
        }
    )
    done = Extraction.model_validate(
        {
            "intent": "log_transactions",
            "confidence": 0.9,
            "transactions": [
                {
                    "kind": "expense",
                    "amount": 15,
                    "currency": "USD",
                    "currency_confidence": 0.9,
                    "description": "almuerzo",
                }
            ],
        }
    )
    s = Setup(ask, done)
    await s.service.register_text(USER, "gasté en el almuerzo")
    outcome = await s.service.register_text(USER, "15 dólares")
    assert isinstance(outcome, Saved)
    assert s.store.batches[0][0].raw_text == "gasté en el almuerzo / 15 dólares"


async def test_deshacer_un_cambio() -> None:
    s = Setup(exchange(from_amount=50, rate=985))
    outcome = await s.service.register_text(USER, "...")
    assert isinstance(outcome, ExchangeSaved)
    assert await s.service.undo_exchange(USER, outcome.exchange.id) == 1
    assert await s.service.undo_exchange(USER, outcome.exchange.id) == 0


async def test_respuesta_etiquetada_como_correccion_igual_completa_el_cambio() -> None:
    """Con Gemini real, «a 980» tras la pregunta llegó como `correction` con el cambio lleno."""
    completed = exchange(from_amount=50, rate=980).model_copy(update={"intent": "correction"})
    s = Setup(exchange(from_amount=50), completed)
    await s.service.register_text(USER, "cambié 50 usdt a bs")
    assert isinstance(await s.service.register_text(USER, "a 980"), ExchangeSaved)


async def test_correccion_sin_pregunta_pendiente_no_es_un_cambio() -> None:
    correction = exchange(from_amount=50, rate=980).model_copy(update={"intent": "correction"})
    s = Setup(correction)
    assert await s.service.register_text(USER, "no, era a 980") == NotATransaction("correction")
