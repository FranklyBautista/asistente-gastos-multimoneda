"""Textos y teclados del registro desde texto libre."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from gastos.chat.handlers.transactions import confirmation_text, question_text
from gastos.chat.keyboards import (
    CurrencyChoice,
    UndoCallback,
    choose_currency_keyboard,
    undo_keyboard,
)
from gastos.domain.conversion import Rate, UsdSnapshot
from gastos.domain.currency import Currency
from gastos.domain.transaction import SavedTransaction, TransactionDraft
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
