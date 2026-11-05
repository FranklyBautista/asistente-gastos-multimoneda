from datetime import UTC, datetime
from typing import Any

from aiogram.types import Chat, Message, TelegramObject
from aiogram.types import User as TelegramUser

from gastos.chat.middlewares import TOO_FAST, RateLimitMiddleware


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


class Handler:
    def __init__(self) -> None:
        self.calls = 0

    async def __call__(self, event: TelegramObject, data: dict[str, Any]) -> str:
        self.calls += 1
        return "ok"


class RecordingMessage(Message):
    """Message que guarda las respuestas en vez de enviarlas a Telegram."""

    def model_post_init(self, context: Any) -> None:
        object.__setattr__(self, "_answers", [])

    @property
    def answers(self) -> list[str]:
        return object.__getattribute__(self, "_answers")

    async def answer(self, text: str, **kwargs: Any) -> Any:  # pyright: ignore[reportIncompatibleMethodOverride]
        self.answers.append(text)


def message(user_id: int) -> RecordingMessage:
    return RecordingMessage.model_validate(
        {
            "message_id": 1,
            "date": datetime(2026, 11, 3, tzinfo=UTC),
            "chat": Chat(id=user_id, type="private"),
            "text": "hola",
        }
    )


def data_for(user_id: int) -> dict[str, Any]:
    return {"event_from_user": TelegramUser(id=user_id, is_bot=False, first_name="Ana")}


def test_permite_hasta_el_limite_y_luego_bloquea() -> None:
    clock = Clock()
    limiter = RateLimitMiddleware(3, clock=clock)
    assert [limiter.allow(1) for _ in range(4)] == [True, True, True, False]


def test_la_ventana_se_desliza() -> None:
    clock = Clock()
    limiter = RateLimitMiddleware(2, clock=clock)
    assert limiter.allow(1)
    clock.now += 30
    assert limiter.allow(1)
    assert not limiter.allow(1)
    clock.now += 30  # el primero ya salió de la ventana de 60 s
    assert limiter.allow(1)
    assert not limiter.allow(1)


def test_cada_persona_tiene_su_propio_limite() -> None:
    limiter = RateLimitMiddleware(1, clock=Clock())
    assert limiter.allow(1)
    assert limiter.allow(2)
    assert not limiter.allow(1)


async def test_avisa_una_sola_vez_por_ventana_y_no_procesa() -> None:
    clock = Clock()
    limiter = RateLimitMiddleware(1, clock=clock)
    handler = Handler()
    first, second, third = message(1), message(1), message(1)

    assert await limiter(handler, first, data_for(1)) == "ok"
    assert await limiter(handler, second, data_for(1)) is None
    assert await limiter(handler, third, data_for(1)) is None

    assert handler.calls == 1
    assert second.answers == [TOO_FAST]
    assert third.answers == []  # no se insiste con el aviso

    clock.now += 61
    assert await limiter(handler, message(1), data_for(1)) == "ok"
    assert handler.calls == 2


async def test_sin_usuario_no_limita() -> None:
    handler = Handler()
    limiter = RateLimitMiddleware(1, clock=Clock())
    for _ in range(3):
        await limiter(handler, message(1), {})
    assert handler.calls == 3
