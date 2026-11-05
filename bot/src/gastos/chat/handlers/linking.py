"""Comando /vincular: código para unir esta cuenta de Telegram con la web (ADR 0012)."""

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from gastos.domain.linking import LINK_TTL
from gastos.domain.user import User
from gastos.services.linking import AlreadyLinked, LinkService

router = Router(name="linking")

NEEDS_ONBOARDING = "Antes de empezar, configura tu cuenta con /start."
ALREADY_LINKED = "Tu cuenta de Telegram ya está vinculada con la web."


def link_text(code: str, web_url: str | None) -> str:
    minutes = int(LINK_TTL.total_seconds() // 60)
    where = f"en {web_url}/vincular" if web_url else "en la web, en la página Vincular"
    return (
        f"Tu código para vincular la web es: {code}\n\n"
        f"Inicia sesión y escríbelo {where}. Vence en {minutes} minutos y sirve una sola vez. "
        "No lo compartas: quien lo use verá tus finanzas."
    )


@router.message(Command("vincular"))
async def link(message: Message, user: User, links: LinkService, web_url: str | None) -> None:
    if not user.is_onboarded:
        await message.answer(NEEDS_ONBOARDING)
        return
    result = await links.issue(user)
    if isinstance(result, AlreadyLinked):
        await message.answer(ALREADY_LINKED)
        return
    await message.answer(link_text(result.code, web_url))
