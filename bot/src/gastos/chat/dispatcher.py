"""Arma el Dispatcher de aiogram con middlewares, routers y manejo de errores."""

from collections.abc import Iterable

from aiogram import Dispatcher

from gastos.chat.errors import on_error
from gastos.chat.handlers import general, onboarding, rates, summary, transactions
from gastos.chat.middlewares import (
    AllowlistMiddleware,
    LogContextMiddleware,
    RateLimitMiddleware,
    UserMiddleware,
)
from gastos.services.rates import RateService
from gastos.services.transactions import TransactionService
from gastos.services.users import UserService
from gastos.services.weekly_summary import WeeklySummaryService


def build_dispatcher(
    allowed_ids: Iterable[int],
    users: UserService,
    rate_service: RateService,
    transaction_service: TransactionService,
    summary_service: WeeklySummaryService,
    *,
    messages_per_minute: int,
) -> Dispatcher:
    # `users`, `rates`, `transactions` y `summaries` llegan a los handlers como argumentos.
    dp = Dispatcher(
        users=users,
        rates=rate_service,
        transactions=transaction_service,
        summaries=summary_service,
    )
    # Orden: contexto de logs → lista blanca → usuario. Lo no permitido no toca la BD.
    dp.update.outer_middleware(LogContextMiddleware())
    dp.update.outer_middleware(AllowlistMiddleware(allowed_ids))
    dp.update.outer_middleware(UserMiddleware(users))
    # Solo los mensajes cuentan para el límite: los botones no llaman al LLM.
    dp.message.outer_middleware(RateLimitMiddleware(messages_per_minute))
    dp.errors.register(on_error)
    # transactions toma el texto libre; general va último: tiene el comodín.
    dp.include_routers(
        onboarding.router, rates.router, summary.router, transactions.router, general.router
    )
    return dp
