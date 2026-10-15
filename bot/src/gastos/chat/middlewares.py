"""Middlewares: contexto de logs, lista blanca y carga del usuario."""

import time
from collections.abc import Awaitable, Callable, Iterable
from typing import Any

import structlog
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update
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
