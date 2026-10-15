from datetime import UTC, datetime
from typing import Any

import pytest
from aiogram.types import Chat, ErrorEvent, Message, TelegramObject, Update
from aiogram.types import User as TelegramUser

from gastos.chat.errors import GENERIC_ERROR, INVALID_OPTION, on_error, user_message_for
from gastos.chat.keyboards import (
    OnboardingCallback,
    currency_keyboard,
    timezone_keyboard,
    ves_source_keyboard,
)
from gastos.chat.middlewares import AllowlistMiddleware, UserMiddleware
from gastos.domain.errors import InvalidPreference
from gastos.domain.user import parse_timezone
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
    assert user_message_for(RuntimeError("password=secreta")) == GENERIC_ERROR


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
