"""Repositorio de deudas y pagos con SQL explícito (Fase 11, ADR 0016).

El bot usa credenciales de servicio (se salta la RLS): cada consulta filtra por user_id. Las
reglas que no dependen del bot (moneda del pago, no pagar de más, deudas anuladas) las
garantiza la base: FK compuesta y el trigger `debt_payments_check`.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any, cast
from uuid import UUID

from psycopg import errors
from psycopg_pool import AsyncConnectionPool

from gastos.db.repositories.transactions import insert_transaction
from gastos.domain.currency import Currency
from gastos.domain.debt import Debt, DebtDirection, DebtStatus, NewDebt
from gastos.domain.errors import DebtChanged
from gastos.domain.transaction import NewTransaction, SavedTransaction

_COLUMNS = (
    "debt_id, direction, counterparty, currency, amount, remaining, status, description, "
    "(select name from categories c where c.id = b.category_id), incurred_at"
)


def _to_debt(r: tuple[Any, ...]) -> Debt:
    return Debt(
        id=cast(UUID, r[0]),
        direction=cast(DebtDirection, r[1]),
        counterparty=cast(str, r[2]),
        currency=cast(Currency, r[3]),
        amount=cast(Decimal, r[4]),
        remaining=cast(Decimal, r[5]),
        status=cast(DebtStatus, r[6]),
        description=cast(str | None, r[7]),
        category=cast(str | None, r[8]),
        incurred_at=cast(datetime, r[9]),
    )


class DebtRepository:
    def __init__(self, pool: AsyncConnectionPool) -> None:
        self._pool = pool

    async def insert(self, user_id: UUID, item: NewDebt) -> Debt:
        async with self._pool.connection() as conn:
            cur = await conn.execute(
                "insert into debts (user_id, direction, counterparty, currency, amount, "
                "category_id, description, usd_per_unit, rate_source, amount_usd, raw_text) "
                "values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
                "returning id, incurred_at",
                (
                    user_id,
                    item.direction,
                    item.counterparty,
                    item.currency,
                    item.amount,
                    item.category.id if item.category else None,
                    item.description,
                    item.snapshot.usd_per_unit,
                    item.snapshot.rate_source,
                    item.snapshot.amount_usd,
                    item.raw_text,
                ),
            )
            row = cast(tuple[Any, ...], await cur.fetchone())
        return Debt(
            id=cast(UUID, row[0]),
            direction=item.direction,
            counterparty=item.counterparty,
            currency=item.currency,
            amount=item.amount,
            remaining=item.amount,
            status="open",
            description=item.description,
            category=item.category.name if item.category else None,
            incurred_at=cast(datetime, row[1]),
        )

    async def list(
        self,
        user_id: UUID,
        *,
        direction: DebtDirection | None = None,
        include_settled: bool = False,
    ) -> list[Debt]:
        """Deudas vigentes: pendientes primero (las más viejas arriba), luego las liquidadas."""
        async with self._pool.connection() as conn:
            cur = await conn.execute(
                f"select {_COLUMNS} from debt_balances b "
                "where user_id = %s and (%s::text is null or direction = %s) "
                "and (%s or status <> 'settled') "
                "order by status = 'settled', incurred_at, debt_id",
                (user_id, direction, direction, include_settled),
            )
            rows = await cur.fetchall()
        return [_to_debt(r) for r in rows]

    async def get(self, user_id: UUID, debt_id: UUID) -> Debt | None:
        async with self._pool.connection() as conn:
            cur = await conn.execute(
                f"select {_COLUMNS} from debt_balances b where user_id = %s and debt_id = %s",
                (user_id, debt_id),
            )
            row = await cur.fetchone()
        return None if row is None else _to_debt(row)

    async def pay(
        self,
        user_id: UUID,
        debt: Debt,
        amount: Decimal,
        movement: NewTransaction | None,
        raw_text: str,
    ) -> tuple[UUID, SavedTransaction | None, Debt]:
        """Guarda el pago y, si movió dinero, su gasto o ingreso, en una sola transacción SQL.

        Lanza DebtChanged si la deuda se anuló o ya no admite ese monto (otro pago llegó
        antes); en ese caso no queda nada guardado.
        """
        try:
            async with self._pool.connection() as conn, conn.transaction():
                saved = (
                    None if movement is None else await insert_transaction(conn, user_id, movement)
                )
                cur = await conn.execute(
                    "insert into debt_payments (user_id, debt_id, currency, amount, "
                    "transaction_id, raw_text) values (%s, %s, %s, %s, %s, %s) returning id",
                    (
                        user_id,
                        debt.id,
                        debt.currency,
                        amount,
                        saved.id if saved else None,
                        raw_text,
                    ),
                )
                payment_id = cast(UUID, cast(tuple[Any, ...], await cur.fetchone())[0])
                cur = await conn.execute(
                    f"select {_COLUMNS} from debt_balances b where user_id = %s and debt_id = %s",
                    (user_id, debt.id),
                )
                after = _to_debt(cast(tuple[Any, ...], await cur.fetchone()))
        except (errors.RaiseException, errors.ForeignKeyViolation) as exc:
            raise DebtChanged(str(exc)) from exc
        return payment_id, saved, after

    async def cancel(self, user_id: UUID, debt_id: UUID) -> int:
        """Anula una deuda registrada por error (Deshacer). 0 si ya estaba anulada o tiene
        pagos vigentes: una deuda con pagos se deshace pago por pago."""
        async with self._pool.connection() as conn:
            cur = await conn.execute(
                "update debts d set cancelled_at = now() "
                "where d.id = %s and d.user_id = %s and d.cancelled_at is null "
                "and not exists (select 1 from debt_payments p "
                "                where p.debt_id = d.id and p.deleted_at is null)",
                (debt_id, user_id),
            )
            return cur.rowcount

    async def undo_payment(self, user_id: UUID, payment_id: UUID) -> int:
        """Deshace un pago y borra (lógicamente) el movimiento que creó, juntos."""
        async with self._pool.connection() as conn, conn.transaction():
            cur = await conn.execute(
                "update debt_payments set deleted_at = now() "
                "where id = %s and user_id = %s and deleted_at is null "
                "returning transaction_id",
                (payment_id, user_id),
            )
            row = await cur.fetchone()
            if row is None:
                return 0
            if row[0] is not None:
                await conn.execute(
                    "update transactions set deleted_at = now() "
                    "where id = %s and user_id = %s and deleted_at is null",
                    (row[0], user_id),
                )
            return 1
