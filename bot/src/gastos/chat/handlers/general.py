"""Comandos generales y respuesta por defecto a cualquier otro mensaje."""

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from gastos.chat.handlers.onboarding import profile_text
from gastos.domain.user import User

router = Router(name="general")

HELP = (
    "Comandos:\n"
    "/start · configurar moneda por defecto, tasa de Bs y zona horaria\n"
    "/perfil · ver tu configuración\n"
    "/tasas · ver las tasas de cambio vigentes\n"
    "/ayuda · ver esta ayuda\n\n"
    "Para anotar, escribe como hablas: «almuerzo 15 bs», «taxi 20 mil y café 3 dólares» "
    "o «me pagaron 200 usdt». Si no queda clara la moneda, te pregunto con botones."
)
NEEDS_ONBOARDING = "Antes de empezar, configura tu cuenta con /start."
NOT_YET = "Solo entiendo mensajes de texto y los comandos de /ayuda."


@router.message(Command("ayuda", "help"))
async def help_command(message: Message) -> None:
    await message.answer(HELP)


@router.message(Command("perfil"))
async def profile(message: Message, user: User) -> None:
    if not user.is_onboarded:
        await message.answer(NEEDS_ONBOARDING)
        return
    await message.answer(profile_text(user))


@router.message()
async def fallback(message: Message, user: User) -> None:
    await message.answer(NOT_YET if user.is_onboarded else NEEDS_ONBOARDING)
