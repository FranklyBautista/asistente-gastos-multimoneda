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
    "/resumen · cómo va tu semana (también te lo mando el domingo en la tarde)\n"
    "/corregir · corregir lo último que anotaste\n"
    "/deudas · lo que debes y lo que te deben\n"
    "/topes · cómo vas con tus topes del mes\n"
    "/colchon · para cuántos días te alcanza lo que tienes\n"
    "/contexto · activar o apagar el «cómo vas» al anotar\n"
    "/vincular · código para ver tus finanzas en la web\n"
    "/ayuda · ver esta ayuda\n\n"
    "Para anotar, escribe como hablas: «almuerzo 15 bs», «taxi 20 mil y café 3 dólares» "
    "o «me pagaron 200 usdt». Si no queda clara la moneda, te pregunto con botones.\n\n"
    "Para un cambio de moneda: «cambié 50 usdt a bs a 985» o «vendí 100 dólares por "
    "98.500 bs». Te digo cómo te fue frente a la tasa de referencia.\n\n"
    "También puedes preguntarme: «¿cuánto gasté esta semana?», «¿en qué se me fue la plata "
    "el mes pasado?», «¿cuánto tengo en dólares?» o «mis últimos 5 gastos».\n\n"
    "Para deudas: «le debo 20 dólares a miguel» o «luisa me debe 50 mil». Cuando se pague, "
    "«le pagué a miguel» o «luisa me pagó 20 mil» la tacha; te pregunto de qué cuenta salió."
    "\n\n"
    "Para un tope: «no quiero gastar más de 100 dólares al mes en comida». Cada vez que "
    "anotes un gasto de esa categoría te digo cómo vas; «quita el tope de comida» lo quita. "
    "Pregúntame también «¿cuánto me dura la plata?».\n\n"
    "Si me equivoco, corrígeme: «eso fue transporte» o «eran 20 mil pesos». "
    "Lo recuerdo para la próxima vez."
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
