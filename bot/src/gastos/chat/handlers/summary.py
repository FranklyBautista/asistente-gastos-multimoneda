"""Comando /resumen: el resumen de la semana en curso, a pedido."""

from aiogram import Bot, Router
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.utils.chat_action import ChatActionSender

from gastos.domain.user import User
from gastos.services.weekly_summary import WeeklySummaryService

router = Router(name="summary")

NEEDS_ONBOARDING = "Antes de empezar, configura tu cuenta con /start."


@router.message(Command("resumen"))
async def summary(message: Message, bot: Bot, user: User, summaries: WeeklySummaryService) -> None:
    if not user.is_onboarded:
        await message.answer(NEEDS_ONBOARDING)
        return
    async with ChatActionSender.typing(bot=bot, chat_id=message.chat.id):
        result = await summaries.compose(user)
    await message.answer(result.text)
