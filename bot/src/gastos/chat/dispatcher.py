"""Arma el Dispatcher de aiogram con middlewares, routers y manejo de errores."""

from collections.abc import Iterable

from aiogram import Dispatcher

from gastos.chat.errors import on_error
from gastos.chat.handlers import general, onboarding, rates
from gastos.chat.middlewares import AllowlistMiddleware, LogContextMiddleware, UserMiddleware
from gastos.services.rates import RateService
from gastos.services.users import UserService


def build_dispatcher(
    allowed_ids: Iterable[int], users: UserService, rate_service: RateService
) -> Dispatcher:
    # `users` y `rates` llegan a los handlers como argumentos.
    dp = Dispatcher(users=users, rates=rate_service)
    # Orden: contexto de logs → lista blanca → usuario. Lo no permitido no toca la BD.
    dp.update.outer_middleware(LogContextMiddleware())
    dp.update.outer_middleware(AllowlistMiddleware(allowed_ids))
    dp.update.outer_middleware(UserMiddleware(users))
    dp.errors.register(on_error)
    # general va último: tiene el comodín.
    dp.include_routers(onboarding.router, rates.router, general.router)
    return dp
