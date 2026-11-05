"""Middlewares: contexto de logs, lista blanca, límite de mensajes y carga del usuario."""

import time
from collections import deque
from collections.abc import Awaitable, Callable, Iterable
from typing import Any

import structlog
from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject, Update
from aiogram.types import User as TelegramUser

from gastos.services.users import UserService

Handler = Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]]

log = structlog.get_logger()


class LogContextMiddleware(BaseMiddleware):
    """Asocia cada línea de log al update_id y registra la duración del update."""

    async def __call__(self, handler: Handler, event: TelegramObject, data: dict[str, Any]) -> Any:
        structlog.contextvars.clear_contextvars()
        if isinstance(event, Update):
            structlog.contextvars.bind_contextvars(
                update_id=event.update_id, update_type=event.event_type
            )
        started = time.perf_counter()
        try:
            return await handler(event, data)
        finally:
            log.debug("update_handled", ms=round((time.perf_counter() - started) * 1000))


class AllowlistMiddleware(BaseMiddleware):
    """Ignora en silencio los updates de quien no está en ALLOWED_TELEGRAM_IDS."""

    def __init__(self, allowed_ids: Iterable[int]) -> None:
        self._allowed = frozenset(allowed_ids)

    async def __call__(self, handler: Handler, event: TelegramObject, data: dict[str, Any]) -> Any:
        tg_user: TelegramUser | None = data.get("event_from_user")
        if tg_user is None or tg_user.id not in self._allowed:
            log.info("update_ignored", reason="not_allowed", telegram_id=tg_user and tg_user.id)
            return None
        return await handler(event, data)


TOO_FAST = "Vas muy rápido 🙂. Espera un minuto y vuelve a escribirme; no anoté ese mensaje."


class RateLimitMiddleware(BaseMiddleware):
    """Limita los mensajes por minuto de cada persona (ventana deslizante en memoria).

    Cada mensaje de texto puede costar una llamada al LLM; el límite protege la cuota del
    plan gratuito. Al pasarse se avisa una sola vez por ventana y el resto se ignora.
    Vive en memoria: con una sola instancia del bot basta (ver jobs/scheduler.py).
    """

    def __init__(
        self,
        per_minute: int,
        *,
        window_seconds: float = 60,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._limit = per_minute
        self._window = window_seconds
        self._clock = clock
        self._hits: dict[int, deque[float]] = {}
        self._warned_until: dict[int, float] = {}

    def allow(self, telegram_id: int) -> bool:
        now = self._clock()
        hits = self._hits.setdefault(telegram_id, deque())
        while hits and now - hits[0] >= self._window:
            hits.popleft()
        if len(hits) >= self._limit:
            return False
        hits.append(now)
        return True

    def _should_warn(self, telegram_id: int) -> bool:
        now = self._clock()
        if now < self._warned_until.get(telegram_id, 0):
            return False
        self._warned_until[telegram_id] = now + self._window
        return True

    async def __call__(self, handler: Handler, event: TelegramObject, data: dict[str, Any]) -> Any:
        tg_user: TelegramUser | None = data.get("event_from_user")
        if tg_user is None or self.allow(tg_user.id):
            return await handler(event, data)
        log.warning("update_ignored", reason="rate_limited", telegram_id=tg_user.id)
        if isinstance(event, Message) and self._should_warn(tg_user.id):
            await event.answer(TOO_FAST)
        return None


class UserMiddleware(BaseMiddleware):
    """Identifica (o registra) al usuario y lo pasa a los handlers como `user`."""

    def __init__(self, users: UserService) -> None:
        self._users = users

    async def __call__(self, handler: Handler, event: TelegramObject, data: dict[str, Any]) -> Any:
        tg_user: TelegramUser | None = data.get("event_from_user")
        if tg_user is None:
            return await handler(event, data)
        user = await self._users.identify(tg_user.id, tg_user.full_name)
        structlog.contextvars.bind_contextvars(user_id=str(user.id))
        data["user"] = user
        return await handler(event, data)
