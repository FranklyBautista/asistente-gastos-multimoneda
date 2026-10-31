"""Repositorio de movimientos, cuentas y categorías con SQL explícito.

El bot usa credenciales de servicio (se salta la RLS): cada consulta filtra por user_id.
"""

from collections.abc import Sequence
from datetime import datetime
from typing import Any, cast
from uuid import UUID

from psycopg_pool import AsyncConnectionPool

from gastos.domain.account import Account, AccountKind, Category
from gastos.domain.currency import Currency
from gastos.domain.transaction import NewTransaction, SavedTransaction


class TransactionRepository:
    def __init__(self, pool: AsyncConnectionPool) -> None:
        self._pool = pool

    async def accounts(self, user_id: UUID) -> list[Account]:
        """Cuentas activas del usuario, en orden estable (por nombre)."""
        async with self._pool.connection() as conn:
            cur = await conn.execute(
                "select id, name, currency, kind from accounts "
                "where user_id = %s and not archived order by name",
                (user_id,),
            )
            rows = await cur.fetchall()
        return [
            Account(
                id=cast(UUID, r[0]),
                name=cast(str, r[1]),
                currency=cast(Currency, r[2]),
                kind=cast(AccountKind, r[3]),
            )
            for r in rows
        ]

    async def categories(self, user_id: UUID) -> list[Category]:
        """Las globales más las propias del usuario; si un nombre se repite, gana la propia."""
        async with self._pool.connection() as conn:
            cur = await conn.execute(
                "select distinct on (name, kind) id, name, kind from categories "
                "where user_id is null or user_id = %s "
                "order by name, kind, user_id nulls last",
                (user_id,),
            )
            rows = await cur.fetchall()
        return [Category(id=cast(UUID, r[0]), name=cast(str, r[1]), kind=r[2]) for r in rows]

    async def insert_many(
        self, user_id: UUID, items: Sequence[NewTransaction]
    ) -> list[SavedTransaction]:
        """Guarda todos los movimientos de un mensaje en una sola transacción SQL.

        Al compartir transacción comparten `created_at` (now()), que es lo que usa `undo_batch`.
        """
        saved: list[SavedTransaction] = []
        async with self._pool.connection() as conn, conn.transaction():
            for item in items:
                cur = await conn.execute(
                    "insert into transactions (user_id, account_id, currency, kind, amount, "
                    "category_id, description, occurred_at, usd_per_unit, rate_source, "
                    "amount_usd, raw_text, parse_confidence) "
                    "values (%s, %s, %s, %s, %s, %s, %s, coalesce(%s, now()), %s, %s, %s, %s, %s) "
                    "returning id, occurred_at",
                    (
                        user_id,
                        item.account.id,
                        item.currency,
                        item.kind,
                        item.amount,
                        item.category.id,
                        item.description,
                        item.occurred_at,
                        item.snapshot.usd_per_unit,
                        item.snapshot.rate_source,
                        item.snapshot.amount_usd,
                        item.raw_text,
                        round(item.parse_confidence, 2),
                    ),
                )
                row = cast(tuple[Any, ...], await cur.fetchone())
                saved.append(
                    SavedTransaction(
                        id=cast(UUID, row[0]),
                        kind=item.kind,
                        amount=item.amount,
                        currency=item.currency,
                        category=item.category.name,
                        description=item.description,
                        account_name=item.account.name,
                        snapshot=item.snapshot,
                        occurred_at=cast(datetime, row[1]),
                    )
                )
        return saved

    async def undo_batch(self, user_id: UUID, transaction_id: UUID) -> int:
        """Borra (lógicamente) el movimiento y los que se guardaron con él en el mismo mensaje.

        Devuelve cuántos se borraron: 0 si ya estaban borrados o no son de ese usuario.
        """
        async with self._pool.connection() as conn:
            cur = await conn.execute(
                "update transactions t set deleted_at = now() "
                "from transactions ref "
                "where ref.id = %s and ref.user_id = %s "
                "and t.user_id = ref.user_id and t.created_at = ref.created_at "
                "and t.raw_text is not distinct from ref.raw_text "
                "and t.deleted_at is null",
                (transaction_id, user_id),
            )
            return cur.rowcount
