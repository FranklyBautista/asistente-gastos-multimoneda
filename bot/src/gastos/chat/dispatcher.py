"""Arma el Dispatcher de aiogram con middlewares, routers y manejo de errores."""

from collections.abc import Iterable

from aiogram import Dispatcher

from gastos.chat.errors import on_error
from gastos.chat.handlers import general, linking, onboarding, rates, summary, transactions
from gastos.chat.middlewares import (
    AllowlistMiddleware,
    DeduplicateMiddleware,
    LogContextMiddleware,
    PerUserOrderMiddleware,
    RateLimitMiddleware,
    UserMiddleware,
)
from gastos.services.linking import LinkService
from gastos.services.rates import RateService
from gastos.services.transactions import TransactionService
from gastos.services.updates import UpdateLedger
from gastos.services.users import UserService
from gastos.services.weekly_summary import WeeklySummaryService


def build_dispatcher(
    allowed_ids: Iterable[int],
    users: UserService,
    rate_service: RateService,
    transaction_service: TransactionService,
    summary_service: WeeklySummaryService,
    updates: UpdateLedger,
    link_service: LinkService,
    *,
    messages_per_minute: int,
    web_url: str | None = None,
) -> Dispatcher:
    # Los kwargs del Dispatcher (`users`, `rates`, `transactions`, `summaries`, `links` y
    # `web_url`) llegan a los handlers como argumentos.
    dp = Dispatcher(
        users=users,
        rates=rate_service,
        transactions=transaction_service,
        summaries=summary_service,
        links=link_service,
        web_url=web_url,
    )
    # Orden: contexto de logs → lista blanca → orden por persona → repetidos → usuario. Lo no
    # permitido no toca la BD; cada persona se atiende de a un update; un update repetido se
    # descarta antes de llegar a los handlers.
    dp.update.outer_middleware(LogContextMiddleware())
    dp.update.outer_middleware(AllowlistMiddleware(allowed_ids))
    dp.update.outer_middleware(PerUserOrderMiddleware())
    dp.update.outer_middleware(DeduplicateMiddleware(updates))
    dp.update.outer_middleware(UserMiddleware(users))
    # Solo los mensajes cuentan para el límite: los botones no llaman al LLM.
    dp.message.outer_middleware(RateLimitMiddleware(messages_per_minute))
    dp.errors.register(on_error)
    # transactions toma el texto libre; general va último: tiene el comodín.
    dp.include_routers(
        onboarding.router,
        rates.router,
        summary.router,
        linking.router,
        transactions.router,
        general.router,
    )
    return dp
