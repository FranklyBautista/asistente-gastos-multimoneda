"""Arma el Dispatcher de aiogram con middlewares, routers y manejo de errores."""

from collections.abc import Iterable

from aiogram import Dispatcher

from gastos.chat.errors import on_error
from gastos.chat.handlers import general, onboarding
from gastos.chat.middlewares import AllowlistMiddleware, LogContextMiddleware, UserMiddleware
from gastos.services.users import UserService


def build_dispatcher(allowed_ids: Iterable[int], users: UserService) -> Dispatcher:
    dp = Dispatcher(users=users)  # `users` llega a los handlers como argumento
    # Orden: contexto de logs → lista blanca → usuario. Lo no permitido no toca la BD.
    dp.update.outer_middleware(LogContextMiddleware())
    dp.update.outer_middleware(AllowlistMiddleware(allowed_ids))
    dp.update.outer_middleware(UserMiddleware(users))
    dp.errors.register(on_error)
    dp.include_routers(onboarding.router, general.router)  # general va último: tiene el comodín
    return dp
