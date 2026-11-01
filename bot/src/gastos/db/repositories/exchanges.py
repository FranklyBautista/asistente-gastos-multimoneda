"""Repositorio de cambios entre monedas con SQL explícito.

Las FK compuestas de `exchanges` garantizan que ambas cuentas son del mismo usuario; aun así,
cada consulta filtra por user_id (el bot se salta la RLS).
"""

from datetime import datetime
from typing import Any, cast
from uuid import UUID

from psycopg_pool import AsyncConnectionPool

from gastos.domain.exchange import NewExchange, SavedExchange


class ExchangeRepository:
    def __init__(self, pool: AsyncConnectionPool) -> None:
        self._pool = pool

    async def insert(self, user_id: UUID, item: NewExchange) -> SavedExchange:
        amounts = item.amounts
        async with self._pool.connection() as conn:
            cur = await conn.execute(
                "insert into exchanges (user_id, from_account_id, to_account_id, from_amount, "
                "to_amount, effective_rate, reference_rate, occurred_at, raw_text) "
                "values (%s, %s, %s, %s, %s, %s, %s, coalesce(%s, now()), %s) "
                "returning id, occurred_at",
                (
                    user_id,
                    item.from_account.id,
                    item.to_account.id,
                    amounts.from_amount,
                    amounts.to_amount,
                    amounts.effective_rate,
                    item.reference_rate,
                    item.occurred_at,
                    item.raw_text,
                ),
            )
            row = cast(tuple[Any, ...], await cur.fetchone())
        return SavedExchange(
            id=cast(UUID, row[0]),
            from_currency=item.from_account.currency,
            to_currency=item.to_account.currency,
            amounts=amounts,
            reference_rate=item.reference_rate,
            from_account_name=item.from_account.name,
            to_account_name=item.to_account.name,
            occurred_at=cast(datetime, row[1]),
        )

    async def undo(self, user_id: UUID, exchange_id: UUID) -> int:
        """Borra (lógicamente) el cambio; 0 si ya estaba borrado o no es de ese usuario."""
        async with self._pool.connection() as conn:
            cur = await conn.execute(
                "update exchanges set deleted_at = now() "
                "where id = %s and user_id = %s and deleted_at is null",
                (exchange_id, user_id),
            )
            return cur.rowcount
