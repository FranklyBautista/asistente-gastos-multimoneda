"""Manejo central de errores: se registra el fallo y el usuario recibe un mensaje claro."""

import structlog
from aiogram import Bot
from aiogram.types import ErrorEvent

from gastos.domain.errors import (
    AccountNotFound,
    DomainError,
    InvalidPreference,
    LLMUnavailable,
    RateUnavailable,
)

log = structlog.get_logger()

GENERIC_ERROR = "Algo salió mal y no pude procesarlo. Inténtalo de nuevo en un momento."
INVALID_OPTION = "Esa opción ya no es válida. Escribe /start para empezar de nuevo."
NO_RATE = "Todavía no tengo la tasa de cambio de esa moneda. Inténtalo de nuevo en unos minutos."
LLM_DOWN = (
    "No pude entender el mensaje porque el servicio de IA no está respondiendo. "
    "No anoté nada; inténtalo de nuevo en un momento."
)
NO_ACCOUNT = "No tienes ninguna cuenta activa en esa moneda, así que no anoté nada."


def user_message_for(exc: Exception) -> str:
    """Traduce una excepción a un mensaje para el usuario, sin detalles internos."""
    if isinstance(exc, InvalidPreference):
        return INVALID_OPTION
    if isinstance(exc, RateUnavailable):
        return NO_RATE
    if isinstance(exc, LLMUnavailable):
        return LLM_DOWN
    if isinstance(exc, AccountNotFound):
        return NO_ACCOUNT
    return GENERIC_ERROR


def _chat_id(event: ErrorEvent) -> int | None:
    update = event.update
    if update.message:
        return update.message.chat.id
    if update.callback_query and update.callback_query.message:
        return update.callback_query.message.chat.id
    return None


async def on_error(event: ErrorEvent, bot: Bot) -> bool:
    exc = event.exception
    if isinstance(exc, DomainError):
        log.warning("update_rejected", error=type(exc).__name__)
    else:
        log.error("update_failed", error=type(exc).__name__, exc_info=exc)

    text = user_message_for(exc)
    try:
        if event.update.callback_query:
            await event.update.callback_query.answer()
        chat_id = _chat_id(event)
        if chat_id is not None:
            await bot.send_message(chat_id, text)
    except Exception as notify_exc:  # avisar al usuario nunca debe tumbar el bot
        log.error("error_notification_failed", error=type(notify_exc).__name__)
    return True
