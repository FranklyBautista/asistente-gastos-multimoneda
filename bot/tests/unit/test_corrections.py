"""Correcciones del último movimiento y su uso como ejemplos del prompt."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from gastos.chat.handlers.transactions import (
    NOTHING_TO_CORRECT,
    correction_text,
    last_movements_text,
)
from gastos.domain.account import Category
from gastos.domain.conversion import Rate, UsdSnapshot
from gastos.domain.correction import (
    Change,
    CorrectionDraft,
    CorrectionExample,
    StoredTransaction,
    pick_target,
    rescale_snapshot,
)
from gastos.extraction.prompt import corrections_section, system_prompt
from gastos.extraction.schema import Extraction
from gastos.services.corrections import (
    Corrected,
    CorrectionService,
    NoChange,
    NothingToCorrect,
    as_saved,
)
from gastos.services.exchanges import ExchangeService
from gastos.services.outcomes import Ask
from gastos.services.query_tools import QueryService
from gastos.services.rates import RateService
from gastos.services.transactions import TransactionService
from tests.fakes import (
    FakeCorrectionStore,
    FakeExchangeStore,
    FakeExtractor,
    FakeRateSources,
    FakeRateStore,
    FakeReportStore,
    FakeTransactionStore,
    make_user,
)

D = Decimal
NOW = datetime(2026, 11, 2, 15, tzinfo=UTC)
CREATED = NOW - timedelta(minutes=5)
USER = make_user(onboarded=True)  # Caracas, Bs con tasa paralela
TX_STORE = FakeTransactionStore()
ACCOUNTS = {a.name: a for a in TX_STORE.account_list}
CATEGORIES = {(c.name, c.kind): c for c in TX_STORE.category_list}


def stored(
    description: str = "taxi",
    amount: str = "20000",
    account: str = "efectivo USD",
    category: str = "comida",
    usd_per_unit: str = "1",
) -> StoredTransaction:
    acc = ACCOUNTS[account]
    snapshot = UsdSnapshot(D(usd_per_unit), "pivot" if acc.currency == "USD" else "fx", D(0))
    return StoredTransaction(
        id=uuid4(),
        kind="expense",
        amount=D(amount),
        account=acc,
        category=CATEGORIES[(category, "expense")],
        description=description,
        snapshot=rescale_snapshot(D(amount), snapshot),
        occurred_at=CREATED,
        created_at=CREATED,
        raw_text=f"{description} {amount}",
    )


def rates(*items: Rate) -> RateService:
    unused = RuntimeError("no se refresca en estas pruebas")
    sources = FakeRateSources(dolarapi=unused, p2p=unused, cop=unused, usdt=unused)
    return RateService(FakeRateStore(*items), sources, timedelta(hours=6), clock=lambda: NOW)


def service(store: FakeCorrectionStore, *items: Rate) -> CorrectionService:
    return CorrectionService(store, TX_STORE, rates(*items))  # las mismas cuentas y categorías


# ---- Dominio ----


def test_con_un_solo_movimiento_no_hace_falta_pista() -> None:
    only = stored()
    assert pick_target([only], None) == only


def test_con_varios_la_pista_elige_por_descripcion_o_categoria() -> None:
    lunch, coffee = stored("almuerzo"), stored("café")
    assert pick_target([lunch, coffee], "el café") == coffee
    assert pick_target([lunch, coffee], None) is None
    assert pick_target([lunch, coffee], "comida") is None  # coinciden los dos: no se adivina


def test_cambiar_el_monto_conserva_la_tasa() -> None:
    snapshot = UsdSnapshot(D("0.00025"), "fx", D(5))
    assert rescale_snapshot(D(40000), snapshot) == UsdSnapshot(D("0.00025"), "fx", D("10"))


# ---- Servicio ----


async def test_corrige_la_categoria_y_lo_registra() -> None:
    target = stored()
    store = FakeCorrectionStore([target])
    outcome = await service(store).correct(
        USER, CorrectionDraft(category="Transporte"), "eso fue transporte"
    )
    assert isinstance(outcome, Corrected)
    assert outcome.transaction.category == "transporte"
    assert outcome.changes == [Change("category", "comida", "transporte")]
    tx_id, values, _, raw_text = store.applied[0]
    assert (tx_id, values.amount, raw_text) == (target.id, D(20000), "eso fue transporte")


async def test_otra_moneda_usa_la_tasa_de_cuando_se_anoto() -> None:
    old = Rate("COP", "fx", D("0.00025"), CREATED - timedelta(hours=1))
    newer = Rate("COP", "fx", D("0.0003"), NOW)
    store = FakeCorrectionStore([stored()])
    outcome = await service(store, old, newer).correct(
        USER, CorrectionDraft(currency="COP"), "no, eran pesos"
    )
    assert isinstance(outcome, Corrected)
    tx = outcome.transaction
    assert (tx.currency, tx.account_name) == ("COP", "efectivo COP")
    assert tx.snapshot == UsdSnapshot(D("0.00025"), "fx", D("5.000000"))
    assert outcome.changes == [Change("currency", "USD", "COP")]


async def test_monto_y_moneda_a_la_vez() -> None:
    store = FakeCorrectionStore([stored(amount="20")])
    outcome = await service(store, Rate("COP", "fx", D("0.00025"), CREATED)).correct(
        USER, CorrectionDraft(currency="COP", amount=D(20000)), "eran 20 mil pesos"
    )
    assert isinstance(outcome, Corrected)
    assert [c.field for c in outcome.changes] == ["currency", "amount"]
    assert outcome.transaction.snapshot.amount_usd == D("5.000000")


async def test_pasar_a_ingreso_cambia_a_una_categoria_de_ingreso() -> None:
    store = FakeCorrectionStore([stored()])
    outcome = await service(store).correct(USER, CorrectionDraft(kind="income"), "era ingreso")
    assert isinstance(outcome, Corrected)
    assert outcome.transaction.category == "otros ingresos"
    assert [c.field for c in outcome.changes] == ["kind", "category"]


async def test_cuenta_de_la_misma_moneda_solo_si_coincide() -> None:
    store = FakeCorrectionStore([stored(account="efectivo Bs", usd_per_unit="0.001")])
    outcome = await service(store).correct(
        USER, CorrectionDraft(account_hint="banesco"), "fue con banesco"
    )
    assert isinstance(outcome, Corrected)
    assert outcome.changes == [Change("account", "efectivo Bs", "banesco")]
    unknown = await service(FakeCorrectionStore([stored(account="efectivo Bs")])).correct(
        USER, CorrectionDraft(account_hint="mercantil"), "fue con mercantil"
    )
    assert isinstance(unknown, NoChange)  # no se cambia a una cuenta que no nombró


async def test_categoria_que_no_existe_se_pregunta() -> None:
    outcome = await service(FakeCorrectionStore([stored()])).correct(
        USER, CorrectionDraft(category="mascotas"), "eso fue mascotas"
    )
    assert isinstance(outcome, Ask)
    assert "mascotas" in outcome.question and "transporte" in outcome.question


async def test_varios_movimientos_sin_pista_se_pregunta_cual() -> None:
    store = FakeCorrectionStore([stored("almuerzo"), stored("café")])
    outcome = await service(store).correct(USER, CorrectionDraft(currency="VES"), "era en bs")
    assert isinstance(outcome, Ask)
    assert "almuerzo, café" in outcome.question
    assert store.applied == []


async def test_sin_movimientos_o_sin_cambios() -> None:
    nothing = await service(FakeCorrectionStore()).correct(
        USER, CorrectionDraft(category="ocio"), "eso fue ocio"
    )
    assert isinstance(nothing, NothingToCorrect)
    same = await service(FakeCorrectionStore([stored()])).correct(
        USER, CorrectionDraft(category="comida"), "eso fue comida"
    )
    assert isinstance(same, NoChange)
    empty = await service(FakeCorrectionStore([stored()])).correct(USER, CorrectionDraft(), "x")
    assert isinstance(empty, Ask)


async def test_si_se_deshizo_mientras_tanto_no_hay_nada_que_corregir() -> None:
    store = FakeCorrectionStore([stored()])
    store.gone = True
    outcome = await service(store).correct(USER, CorrectionDraft(category="ocio"), "ocio")
    assert isinstance(outcome, NothingToCorrect)


# ---- Flujo completo desde el texto y aprendizaje ----


def transactions_service(
    extractor: FakeExtractor, store: FakeCorrectionStore
) -> TransactionService:
    tx_store = FakeTransactionStore()
    rate_service = rates()
    return TransactionService(
        tx_store,
        extractor,
        rate_service,
        ExchangeService(FakeExchangeStore(), tx_store, rate_service),
        QueryService(FakeReportStore(), tx_store, rate_service),
        CorrectionService(store, tx_store, rate_service),
        clock=lambda: NOW,
    )


def correction(**fields: object) -> Extraction:
    return Extraction.model_validate(
        {"intent": "correction", "confidence": 0.9, "correction": fields}
    )


async def test_el_mensaje_de_correccion_llega_al_servicio() -> None:
    store = FakeCorrectionStore([stored()])
    svc = transactions_service(FakeExtractor(correction(category="transporte")), store)
    outcome = await svc.register_text(USER, "eso fue transporte")
    assert isinstance(outcome, Corrected)


async def test_corregir_con_comando_avisa_al_llm_que_es_una_correccion() -> None:
    store = FakeCorrectionStore([stored()])
    extractor = FakeExtractor(correction(kind="income"))
    outcome = await transactions_service(extractor, store).correct_text(USER, "era un ingreso")
    assert isinstance(outcome, Corrected)
    assert extractor.calls[0][0] == "Corrige el último movimiento: era un ingreso"
    assert store.applied[0][3] == "era un ingreso"  # se guarda lo que escribió


async def test_las_correcciones_pasadas_van_al_extractor() -> None:
    examples = [CorrectionExample("taxi 20 mil", "currency", "COP")]
    store = FakeCorrectionStore([stored()], examples=examples)
    extractor = FakeExtractor(correction(category="ocio"))
    await transactions_service(extractor, store).register_text(USER, "eso fue ocio")
    assert extractor.examples == [examples]


def test_el_prompt_incluye_las_correcciones_como_ejemplos() -> None:
    examples = [
        CorrectionExample("taxi 20 mil", "currency", "COP"),
        CorrectionExample("condominio 30", "category", "servicios"),
        CorrectionExample("me pagó juan 50", "account", "banesco"),
    ]
    section = corrections_section(examples)
    assert "- «taxi 20 mil» -> currency: COP" in section
    assert "- «me pagó juan 50» -> account_hint: banesco" in section
    now = datetime(2026, 11, 2, 11, tzinfo=UTC)
    assert section in system_prompt(["comida"], ["salario"], now, examples)
    assert "Correcciones que hizo" not in system_prompt(["comida"], ["salario"], now)


# ---- Textos del chat ----


def test_texto_de_la_correccion() -> None:
    tx = replace(stored(), category=Category(uuid4(), "transporte", "expense"))
    outcome = Corrected(
        as_saved(tx),
        [Change("category", "comida", "transporte"), Change("currency", "USD", "COP")],
    )
    text = correction_text(outcome, USER, NOW)
    assert text.startswith("✏️ Corregido: Gasto · 20.000,00 USD · transporte · taxi")
    assert text.endswith("(categoría: comida → transporte; moneda: USD → COP)")


def test_texto_de_cambios_de_tipo_y_monto() -> None:
    outcome = Corrected(
        as_saved(stored()),
        [Change("kind", "expense", "income"), Change("amount", "15", "20000")],
    )
    assert "(tipo: gasto → ingreso; monto: 15 → 20.000)" in correction_text(outcome, USER, NOW)


def test_texto_del_ultimo_mensaje() -> None:
    text = last_movements_text([as_saved(stored("almuerzo"))], USER, NOW)
    assert text.startswith("Tu último mensaje anotó:\n• Gasto · 20.000,00 USD · comida · almuerzo")
    assert last_movements_text([], USER, NOW) == NOTHING_TO_CORRECT
