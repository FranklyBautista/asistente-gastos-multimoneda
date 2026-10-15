"""Onboarding con /start: moneda por defecto, fuente de tasa de Bs y zona horaria."""

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from gastos.chat.keyboards import (
    CURRENCY_LABELS,
    TIMEZONE_LABELS,
    VES_SOURCE_LABELS,
    OnboardingCallback,
    currency_keyboard,
    timezone_keyboard,
    ves_source_keyboard,
)
from gastos.domain.user import User
from gastos.services.users import UserService

router = Router(name="onboarding")

ASK_CURRENCY = (
    "¡Hola! Voy a registrar tus gastos en su moneda original.\n\n"
    "1/3 · Cuando escribas un monto sin moneda (por ejemplo «almuerzo 15»), "
    "¿cuál uso por defecto?"
)
ASK_VES_SOURCE = "2/3 · ¿Qué tasa usas para convertir tus bolívares a dólares?"
ASK_TIMEZONE = "3/3 · ¿En qué zona horaria estás? La uso para «hoy» y «esta semana»."


def profile_text(user: User) -> str:
    timezone = TIMEZONE_LABELS.get(user.timezone, user.timezone)
    return (
        f"Moneda por defecto: {CURRENCY_LABELS[user.default_currency]}\n"
        f"Tasa de Bs: {VES_SOURCE_LABELS[user.ves_rate_source]}\n"
        f"Zona horaria: {timezone}"
    )


@router.message(CommandStart())
async def start(message: Message) -> None:
    await message.answer(ASK_CURRENCY, reply_markup=currency_keyboard())


async def _next_step(query: CallbackQuery, text: str, markup: InlineKeyboardMarkup | None) -> None:
    """Edita el mensaje de la pregunta anterior para no llenar el chat de mensajes."""
    if isinstance(query.message, Message):
        await query.message.edit_text(text, reply_markup=markup)
    await query.answer()


@router.callback_query(OnboardingCallback.filter(F.step == "currency"))
async def choose_currency(
    query: CallbackQuery, callback_data: OnboardingCallback, user: User, users: UserService
) -> None:
    await users.choose_currency(user, callback_data.value)
    await _next_step(query, ASK_VES_SOURCE, ves_source_keyboard())


@router.callback_query(OnboardingCallback.filter(F.step == "ves"))
async def choose_ves_source(
    query: CallbackQuery, callback_data: OnboardingCallback, user: User, users: UserService
) -> None:
    await users.choose_ves_rate_source(user, callback_data.value)
    await _next_step(query, ASK_TIMEZONE, timezone_keyboard())


@router.callback_query(OnboardingCallback.filter(F.step == "tz"))
async def choose_timezone(
    query: CallbackQuery, callback_data: OnboardingCallback, user: User, users: UserService
) -> None:
    user = await users.finish_onboarding(user, callback_data.value)
    done = f"Listo, ya estás configurado.\n\n{profile_text(user)}\n\nPuedes cambiarlo con /start."
    await _next_step(query, done, None)
