"""Repositorio de correcciones: el último mensaje anotado, aplicar cambios y leer ejemplos.

El bot usa credenciales de servicio (se salta la RLS): cada consulta filtra por user_id.
"""

from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal
from typing import Any, cast
from uuid import UUID

from psycopg_pool import AsyncConnectionPool

from gastos.domain.account import Account, AccountKind, Category
from gastos.domain.conversion import UsdSnapshot
from gastos.domain.correction import (
    Change,
    CorrectedValues,
    CorrectionExample,
    CorrectionField,
    StoredTransaction,
)
from gastos.domain.currency import Currency
from gastos.domain.transaction import TransactionKind

# Los movimientos del último mensaje: comparten created_at y raw_text (ver undo_batch).
_LAST_BATCH = """
with last as (
  select created_at, raw_text from transactions
  where user_id = %(user_id)s and deleted_at is null
  order by created_at desc limit 1
)
select t.id, t.kind, t.amount, a.id, a.name, a.currency, a.kind, c.id, c.name, c.kind,
       t.description, t.usd_per_unit, t.rate_source, t.amount_usd, t.occurred_at,
       t.created_at, t.raw_text
from transactions t
join last l on t.created_at = l.created_at and t.raw_text is not distinct from l.raw_text
join accounts a on a.id = t.account_id
join categories c on c.id = t.category_id
where t.user_id = %(user_id)s and t.deleted_at is null
order by t.description, t.id
"""

# La corrección más reciente de cada (mensaje, campo), de la más nueva a la más vieja.
_EXAMPLES = """
select raw_text, field, new_value from (
  select distinct on (t.raw_text, c.field) t.raw_text, c.field, c.new_value, c.created_at
  from corrections c join transactions t on t.id = c.transaction_id
  where c.user_id = %s and t.user_id = c.user_id and t.raw_text is not null
  order by t.raw_text, c.field, c.created_at desc
) latest
order by created_at desc
limit %s
"""


def _to_stored(r: tuple[Any, ...]) -> StoredTransaction:
    return StoredTransaction(
        id=cast(UUID, r[0]),
        kind=cast(TransactionKind, r[1]),
        amount=cast(Decimal, r[2]),
        account=Account(
            id=cast(UUID, r[3]),
            name=cast(str, r[4]),
            currency=cast(Currency, r[5]),
            kind=cast(AccountKind, r[6]),
        ),
        category=Category(id=cast(UUID, r[7]), name=cast(str, r[8]), kind=r[9]),
        description=cast(str, r[10]),
        snapshot=UsdSnapshot(
            usd_per_unit=cast(Decimal, r[11]),
            rate_source=r[12],
            amount_usd=cast(Decimal, r[13]),
        ),
        occurred_at=cast(datetime, r[14]),
        created_at=cast(datetime, r[15]),
        raw_text=cast(str | None, r[16]),
    )


class CorrectionRepository:
    def __init__(self, pool: AsyncConnectionPool) -> None:
        self._pool = pool

    async def last_batch(self, user_id: UUID) -> list[StoredTransaction]:
        """Los movimientos (no borrados) del último mensaje que anotó el usuario."""
        async with self._pool.connection() as conn:
            cur = await conn.execute(_LAST_BATCH, {"user_id": user_id})
            rows = await cur.fetchall()
        return [_to_stored(r) for r in rows]

    async def apply(
        self,
        user_id: UUID,
        transaction_id: UUID,
        values: CorrectedValues,
        changes: Sequence[Change],
        raw_text: str,
    ) -> bool:
        """Corrige el movimiento y registra cada cambio, en una sola transacción SQL.

        Devuelve False si el movimiento ya no existe (por ejemplo, se deshizo antes).
        """
        async with self._pool.connection() as conn, conn.transaction():
            cur = await conn.execute(
                "update transactions set kind = %s, amount = %s, account_id = %s, "
                "currency = %s, category_id = %s, usd_per_unit = %s, rate_source = %s, "
                "amount_usd = %s "
                "where id = %s and user_id = %s and deleted_at is null",
                (
                    values.kind,
                    values.amount,
                    values.account.id,
                    values.account.currency,
                    values.category.id,
                    values.snapshot.usd_per_unit,
                    values.snapshot.rate_source,
                    values.snapshot.amount_usd,
                    transaction_id,
                    user_id,
                ),
            )
            if cur.rowcount != 1:
                return False
            async with conn.cursor() as insert:
                await insert.executemany(
                    "insert into corrections (user_id, transaction_id, raw_text, field, "
                    "old_value, new_value) values (%s, %s, %s, %s, %s, %s)",
                    [
                        (user_id, transaction_id, raw_text, c.field, c.old_value, c.new_value)
                        for c in changes
                    ],
                )
        return True

    async def recent_examples(self, user_id: UUID, limit: int) -> list[CorrectionExample]:
        """Las últimas correcciones, con el mensaje original del movimiento que corrigieron."""
        async with self._pool.connection() as conn:
            cur = await conn.execute(_EXAMPLES, (user_id, limit))
            rows = await cur.fetchall()
        return [
            CorrectionExample(
                raw_text=cast(str, r[0]),
                field=cast(CorrectionField, r[1]),
                new_value=cast(str, r[2]),
            )
            for r in rows
        ]
