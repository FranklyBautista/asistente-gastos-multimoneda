"""Textos y teclados del registro desde texto libre."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from gastos.chat.handlers.transactions import confirmation_text, exchange_text, question_text
from gastos.chat.keyboards import (
    CurrencyChoice,
    UndoCallback,
    UndoExchangeCallback,
    choose_currency_keyboard,
    undo_exchange_keyboard,
    undo_keyboard,
)
from gastos.domain.conversion import Rate, UsdSnapshot
from gastos.domain.currency import Currency, QuotedCurrency, RateSource
from gastos.domain.exchange import ExchangeAmounts, SavedExchange
from gastos.domain.transaction import SavedTransaction, TransactionDraft
from gastos.services.exchanges import ExchangeSaved
from gastos.services.rates import CurrentRate
from gastos.services.transactions import Saved
from tests.fakes import make_user

NOW = datetime(2026, 10, 31, 19, tzinfo=UTC)  # 15:00 en Caracas
USER = make_user(onboarded=True)


def saved(
    amount: str,
    currency: Currency,
    category: str,
    description: str,
    usd: str,
    occurred_at: datetime = NOW,
) -> SavedTransaction:
    return SavedTransaction(
        id=uuid4(),
        kind="expense",
        amount=Decimal(amount),
        currency=currency,
        category=category,
        description=description,
        account_name="x",
        snapshot=UsdSnapshot(Decimal(1), "pivot", Decimal(usd)),
        occurred_at=occurred_at,
    )


def test_confirmacion_de_un_movimiento_en_una_linea() -> None:
    text = confirmation_text(
        Saved([saved("70", "VES", "transporte", "pasaje", "0.07")], []), USER, NOW
    )
    assert text == "✅ Gasto · 70,00 Bs · transporte · pasaje (≈ 0,07 USD)"


def test_confirmacion_de_varios_con_fecha_y_tasa_vieja() -> None:
    stale = Rate("VES", "parallel", Decimal("0.001"), NOW - timedelta(hours=8))
    batch = [
        saved("20000", "COP", "transporte", "taxi", "5"),
        saved("15", "USD", "comida", "comida", "15", NOW - timedelta(days=1)),
    ]
    assert confirmation_text(Saved(batch, [stale]), USER, NOW).splitlines() == [
        "✅ Anotado:",
        "Gasto · 20.000 COP · transporte · taxi (≈ 5,00 USD)",
        "Gasto · 15,00 USD · comida · 30/10",
        "",
        "⚠️ La tasa de Bs lleva 8 h sin actualizarse; usé la última guardada.",
    ]


def test_pregunta_solo_por_los_dudosos() -> None:
    sure = TransactionDraft("expense", Decimal(70), "VES", 0.95, "pasaje")
    doubt = TransactionDraft("expense", Decimal(15), None, 0, "almuerzo")
    assert question_text([sure, doubt]) == "¿15 en qué moneda? (almuerzo)"
    other = TransactionDraft("expense", Decimal("3.5"), None, 0, "café")
    assert question_text([doubt, other]).splitlines() == [
        "¿En qué moneda fueron estos?",
        "• almuerzo: 15",
        "• café: 3,50",
    ]


def test_botones_de_moneda_con_la_preferida_primero_y_en_64_bytes() -> None:
    markup = choose_currency_keyboard("abcdefgh", "COP")
    buttons = markup.inline_keyboard[0]
    assert [b.text for b in buttons] == ["COP", "Bs", "USD", "USDT"]
    for button in buttons:
        assert button.callback_data is not None
        assert len(button.callback_data.encode()) <= 64
        assert CurrencyChoice.unpack(button.callback_data).token == "abcdefgh"


def test_boton_deshacer_cabe_en_64_bytes() -> None:
    tx_id = str(uuid4())
    [[button]] = undo_keyboard(tx_id).inline_keyboard
    assert button.callback_data is not None
    assert len(button.callback_data.encode()) <= 64
    assert UndoCallback.unpack(button.callback_data).transaction_id == tx_id


def saved_exchange(
    source: Currency, target: Currency, give: str, get: str, reference: str | None
) -> SavedExchange:
    from_amount, to_amount = Decimal(give), Decimal(get)
    return SavedExchange(
        id=uuid4(),
        from_currency=source,
        to_currency=target,
        amounts=ExchangeAmounts(from_amount, to_amount, to_amount / from_amount),
        reference_rate=None if reference is None else Decimal(reference),
        from_account_name="a",
        to_account_name="b",
        occurred_at=NOW,
    )


def current(currency: QuotedCurrency, source: RateSource, age_h: int = 0) -> CurrentRate:
    rate = Rate(currency, source, Decimal("0.001"), NOW - timedelta(hours=age_h))
    return CurrentRate(rate, stale=age_h > 6)


def test_confirmacion_de_venta_de_usdt() -> None:
    ex = saved_exchange("USDT", "VES", "50", "49250", "999")
    rates = [current("USDT", "coingecko"), current("VES", "p2p")]
    text = exchange_text(ExchangeSaved(ex, Decimal("-1.40"), rates), USER, NOW)
    assert text.splitlines() == [
        "🔁 Cambio · 50,00 USDT → 49.250,00 Bs · a 985,00 Bs por USDT",
        "Referencia (USDT y Bs · P2P): 999,00 Bs por USDT; "
        "recibiste 1,40 % menos que con la referencia.",
    ]


def test_compra_se_muestra_como_se_cotiza_en_la_calle() -> None:
    """Pagar 19.800 Bs por 20 USDT se lee "990 Bs por USDT", no "0,0010 USDT por Bs"."""
    ex = saved_exchange("VES", "USDT", "19800", "20", "0.001001001")
    rates = [current("VES", "parallel", age_h=8), current("USDT", "coingecko")]
    lines = exchange_text(ExchangeSaved(ex, Decimal("0.91"), rates), USER, NOW).splitlines()
    assert lines[0] == "🔁 Cambio · 19.800,00 Bs → 20,00 USDT · a 990,00 Bs por USDT"
    assert lines[1].endswith("999,00 Bs por USDT; recibiste 0,91 % más que con la referencia.")
    assert lines[3].startswith("⚠️ La tasa de Bs lleva 8 h sin actualizarse")


def test_cambio_sin_referencia() -> None:
    ex = saved_exchange("USD", "USDT", "100", "99.5", None)
    lines = exchange_text(ExchangeSaved(ex, None, []), USER, NOW).splitlines()
    assert lines == [
        "🔁 Cambio · 100,00 USD → 99,50 USDT · a 1,0050 USD por USDT",
        "Sin tasa de referencia guardada para comparar.",
    ]


def test_boton_deshacer_cambio_cabe_en_64_bytes() -> None:
    ex_id = str(uuid4())
    [[button]] = undo_exchange_keyboard(ex_id).inline_keyboard
    assert button.callback_data is not None
    assert len(button.callback_data.encode()) <= 64
    assert UndoExchangeCallback.unpack(button.callback_data).exchange_id == ex_id
