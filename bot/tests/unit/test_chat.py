from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from aiogram.types import Chat, ErrorEvent, Message, TelegramObject, Update
from aiogram.types import User as TelegramUser

from gastos.chat.errors import (
    GENERIC_ERROR,
    INVALID_OPTION,
    NO_RATE,
    on_error,
    user_message_for,
)
from gastos.chat.handlers.rates import STALE_NOTE, Board, format_age, rates_text
from gastos.chat.keyboards import (
    OnboardingCallback,
    currency_keyboard,
    timezone_keyboard,
    ves_source_keyboard,
)
from gastos.chat.middlewares import AllowlistMiddleware, UserMiddleware
from gastos.domain.conversion import Rate
from gastos.domain.currency import QuotedCurrency, RateSource
from gastos.domain.errors import InvalidPreference, RateUnavailable
from gastos.domain.user import parse_timezone
from gastos.services.rates import CurrentRate
from gastos.services.users import UserService
from tests.fakes import FakeUserStore


def tg_user(user_id: int) -> TelegramUser:
    return TelegramUser(id=user_id, is_bot=False, first_name="Ana")


class Recorder:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def __call__(self, event: TelegramObject, data: dict[str, Any]) -> str:
        self.calls.append(data)
        return "ok"


async def test_lista_blanca_deja_pasar_a_los_permitidos() -> None:
    handler = Recorder()
    result = await AllowlistMiddleware([1, 2])(
        handler, Update(update_id=1), {"event_from_user": tg_user(2)}
    )
    assert result == "ok"
    assert len(handler.calls) == 1


@pytest.mark.parametrize("data", [{"event_from_user": tg_user(999)}, {}])
async def test_lista_blanca_ignora_al_resto(data: dict[str, Any]) -> None:
    handler = Recorder()
    result = await AllowlistMiddleware([1, 2])(handler, Update(update_id=1), data)
    assert result is None
    assert handler.calls == []


async def test_middleware_de_usuario_inyecta_al_usuario() -> None:
    handler = Recorder()
    store = FakeUserStore()
    await UserMiddleware(UserService(store))(
        handler, Update(update_id=1), {"event_from_user": tg_user(7)}
    )
    assert handler.calls[0]["user"].telegram_id == 7
    assert store.created == 1


def test_los_callbacks_caben_en_64_bytes_y_son_validos() -> None:
    for markup in (currency_keyboard(), ves_source_keyboard(), timezone_keyboard()):
        for row in markup.inline_keyboard:
            for button in row:
                assert button.callback_data is not None
                assert len(button.callback_data.encode()) <= 64
                parsed = OnboardingCallback.unpack(button.callback_data)
                if parsed.step == "tz":
                    parse_timezone(parsed.value)


def test_mensajes_de_error_sin_detalles_internos() -> None:
    assert user_message_for(InvalidPreference("currency", "EUR")) == INVALID_OPTION
    assert user_message_for(RateUnavailable("VES", "p2p")) == NO_RATE
    assert user_message_for(RuntimeError("password=secreta")) == GENERIC_ERROR


def test_tasas_en_formato_local_con_aviso_de_tasa_vieja() -> None:
    now = datetime(2026, 10, 27, 12, tzinfo=UTC)

    def current(currency: QuotedCurrency, source: RateSource, usd: str, age_h: int = 0):
        rate = Rate(currency, source, Decimal(usd), now - timedelta(hours=age_h))
        return (currency, source, CurrentRate(rate, stale=age_h > 6))

    board: Board = [
        current("VES", "bcv", "0.0011270120"),
        current("VES", "parallel", "0.001", age_h=8),
        ("VES", "p2p", None),
        current("COP", "fx", "0.00025"),
        current("USDT", "coingecko", "0.998756"),
    ]
    lines = rates_text(board, "parallel", now).splitlines()
    assert lines[2:7] == [
        "Bs · BCV: 887,30 por USD",
        "Bs · paralelo: 1.000,00 por USD ← la tuya ⚠️ sin actualizar hace 8 h",
        "Bs · P2P: sin datos todavía",
        "COP: 4.000,00 por USD",
        "USDT: 0,9988 USD",
    ]
    assert STALE_NOTE in lines
    assert "Rates By Exchange Rate API" in lines[-1]


@pytest.mark.parametrize(
    ("delta", "expected"),
    [
        (timedelta(seconds=10), "1 min"),
        (timedelta(minutes=45), "45 min"),
        (timedelta(hours=3, minutes=59), "3 h"),
        (timedelta(hours=50), "2 días"),
    ],
)
def test_antiguedad_legible(delta: timedelta, expected: str) -> None:
    assert format_age(delta) == expected


class FakeBot:
    def __init__(self) -> None:
        self.sent: list[tuple[int, str]] = []

    async def send_message(self, chat_id: int, text: str) -> None:
        self.sent.append((chat_id, text))


async def test_un_fallo_responde_con_mensaje_generico() -> None:
    message = Message(
        message_id=1,
        date=datetime(2026, 10, 15, tzinfo=UTC),
        chat=Chat(id=555, type="private"),
        from_user=tg_user(1),
        text="hola",
    )
    event = ErrorEvent(update=Update(update_id=1, message=message), exception=RuntimeError("x"))
    bot = FakeBot()
    assert await on_error(event, bot) is True  # pyright: ignore[reportArgumentType]
    assert bot.sent == [(555, GENERIC_ERROR)]
