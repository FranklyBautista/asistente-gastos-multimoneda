"""Repositorio de topes por categoría (Fase 12) con SQL explícito.

El bot entra con credenciales de servicio (se salta la RLS): cada consulta filtra por user_id.
Lo gastado contra cada tope sale de `ReportRepository`, con los mismos filtros que las
consultas del chat.
"""

from decimal import Decimal
from typing import Any, cast
from uuid import UUID

from psycopg import AsyncConnection
from psycopg_pool import AsyncConnectionPool

from gastos.domain.account import Category
from gastos.domain.budget import Budget

_SELECT = (
    "select b.id, c.name, b.limit_usd from budgets b join categories c on c.id = b.category_id "
)


def _to_budget(row: tuple[Any, ...]) -> Budget:
    return Budget(
        id=cast(UUID, row[0]), category=cast(str, row[1]), limit_usd=cast(Decimal, row[2])
    )


async def _active_for(
    conn: AsyncConnection[Any], user_id: UUID, category_id: UUID
) -> Budget | None:
    """El tope vigente de esa categoría, bloqueado hasta el final de la transacción."""
    cur = await conn.execute(
        _SELECT + "where b.user_id = %s and b.category_id = %s and b.archived_at is null "
        "for update of b",
        (user_id, category_id),
    )
    row = await cur.fetchone()
    return _to_budget(row) if row else None


class BudgetRepository:
    def __init__(self, pool: AsyncConnectionPool) -> None:
        self._pool = pool

    async def active(self, user_id: UUID) -> list[Budget]:
        """Los topes vigentes, por nombre de categoría."""
        async with self._pool.connection() as conn:
            cur = await conn.execute(
                _SELECT + "where b.user_id = %s and b.archived_at is null order by c.name",
                (user_id,),
            )
            rows = await cur.fetchall()
        return [_to_budget(r) for r in rows]

    async def set(
        self, user_id: UUID, category: Category, limit_usd: Decimal, raw_text: str | None
    ) -> tuple[Budget, Budget | None]:
        """Fija el tope de la categoría; si ya tenía uno, lo archiva. Devuelve (nuevo, anterior)."""
        async with self._pool.connection() as conn, conn.transaction():
            previous = await _active_for(conn, user_id, category.id)
            if previous is not None:
                await conn.execute(
                    "update budgets set archived_at = now() where id = %s", (previous.id,)
                )
            cur = await conn.execute(
                "insert into budgets (user_id, category_id, limit_usd, replaces_id, raw_text) "
                "values (%s, %s, %s, %s, %s) returning id",
                (user_id, category.id, limit_usd, previous.id if previous else None, raw_text),
            )
            row = cast(tuple[Any, ...], await cur.fetchone())
        return Budget(cast(UUID, row[0]), category.name, limit_usd), previous

    async def remove(self, user_id: UUID, category: Category) -> Budget | None:
        """Quita el tope vigente de la categoría; None si no tenía."""
        async with self._pool.connection() as conn, conn.transaction():
            previous = await _active_for(conn, user_id, category.id)
            if previous is not None:
                await conn.execute(
                    "update budgets set archived_at = now() where id = %s", (previous.id,)
                )
        return previous

    async def undo(self, user_id: UUID, budget_id: UUID) -> bool:
        """Deshace fijar un tope: lo archiva y restaura el que reemplazó, si lo había.

        False si ya no estaba vigente (deshecho o reemplazado después) o no es del usuario.
        """
        async with self._pool.connection() as conn, conn.transaction():
            cur = await conn.execute(
                "update budgets set archived_at = now() "
                "where id = %s and user_id = %s and archived_at is null "
                "returning replaces_id",
                (budget_id, user_id),
            )
            row = await cur.fetchone()
            if row is None:
                return False
            if row[0] is not None:
                await conn.execute(
                    "update budgets set archived_at = null where id = %s and user_id = %s",
                    (row[0], user_id),
                )
        return True
