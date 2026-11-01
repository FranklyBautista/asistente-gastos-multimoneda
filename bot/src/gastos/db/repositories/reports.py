"""Consultas de solo lectura de las herramientas de la Fase 6, con SQL fijo.

El LLM nunca escribe SQL: elige una herramienta y sus parámetros tipados, y aquí cada filtro
opcional se compone con `psycopg.sql` y parámetros. Todo filtra por user_id y excluye lo
borrado.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any, cast
from uuid import UUID

from psycopg import sql
from psycopg_pool import AsyncConnectionPool

from gastos.domain.currency import Currency
from gastos.domain.reports import AccountBalance, CategoryTotal, CurrencyTotal, TransactionRow
from gastos.domain.transaction import TransactionKind


def _filters(
    user_id: UUID,
    start: datetime,
    end: datetime,
    kind: TransactionKind | None = None,
    currency: Currency | None = None,
    category: str | None = None,
) -> tuple[sql.Composed, list[Any]]:
    clauses = [
        sql.SQL("t.user_id = %s"),
        sql.SQL("t.deleted_at is null"),
        sql.SQL("t.occurred_at >= %s"),
        sql.SQL("t.occurred_at < %s"),
    ]
    params: list[Any] = [user_id, start, end]
    optional: tuple[tuple[sql.SQL, str | None], ...] = (
        (sql.SQL("t.kind = %s"), kind),
        (sql.SQL("t.currency = %s"), currency),
        (sql.SQL("c.name = %s"), category),
    )
    for clause, value in optional:
        if value is not None:
            clauses.append(clause)
            params.append(value)
    return sql.SQL(" and ").join(clauses), params


class ReportRepository:
    def __init__(self, pool: AsyncConnectionPool) -> None:
        self._pool = pool

    async def _fetch(
        self, query: sql.SQL | sql.Composed, params: list[Any]
    ) -> list[tuple[Any, ...]]:
        async with self._pool.connection() as conn:
            cur = await conn.execute(query, params)
            return await cur.fetchall()

    async def spending_by_category(
        self, user_id: UUID, start: datetime, end: datetime, currency: Currency | None
    ) -> list[CategoryTotal]:
        where, params = _filters(user_id, start, end, "expense", currency)
        query = sql.SQL(
            "select c.name, t.currency, sum(t.amount), sum(t.amount_usd), count(*) "
            "from transactions t join categories c on c.id = t.category_id "
            "where {} group by c.name, t.currency "
            "order by sum(t.amount_usd) desc, c.name"
        ).format(where)
        rows = await self._fetch(query, params)
        return [
            CategoryTotal(
                category=cast(str, r[0]),
                currency=cast(Currency, r[1]),
                amount=cast(Decimal, r[2]),
                amount_usd=cast(Decimal, r[3]),
                count=cast(int, r[4]),
            )
            for r in rows
        ]

    async def totals(
        self,
        user_id: UUID,
        kind: TransactionKind,
        start: datetime,
        end: datetime,
        currency: Currency | None,
        category: str | None,
    ) -> list[CurrencyTotal]:
        where, params = _filters(user_id, start, end, kind, currency, category)
        query = sql.SQL(
            "select t.currency, sum(t.amount), sum(t.amount_usd), count(*) "
            "from transactions t join categories c on c.id = t.category_id "
            "where {} group by t.currency order by t.currency"
        ).format(where)
        rows = await self._fetch(query, params)
        return [
            CurrencyTotal(
                currency=cast(Currency, r[0]),
                amount=cast(Decimal, r[1]),
                amount_usd=cast(Decimal, r[2]),
                count=cast(int, r[3]),
            )
            for r in rows
        ]

    async def account_balances(self, user_id: UUID) -> list[AccountBalance]:
        query = sql.SQL(
            "select b.name, b.currency, b.balance from account_balances b "
            "join accounts a on a.id = b.account_id "
            "where b.user_id = %s and not a.archived order by b.currency, b.name"
        )
        rows = await self._fetch(query, [user_id])
        return [
            AccountBalance(
                account_name=cast(str, r[0]),
                currency=cast(Currency, r[1]),
                balance=cast(Decimal, r[2]),
            )
            for r in rows
        ]

    async def list_transactions(
        self,
        user_id: UUID,
        start: datetime,
        end: datetime,
        kind: TransactionKind | None,
        currency: Currency | None,
        category: str | None,
        limit: int,
    ) -> list[TransactionRow]:
        where, params = _filters(user_id, start, end, kind, currency, category)
        query = sql.SQL(
            "select t.occurred_at, t.kind, t.amount, t.currency, c.name, t.description "
            "from transactions t join categories c on c.id = t.category_id "
            "where {} order by t.occurred_at desc, t.created_at desc limit %s"
        ).format(where)
        rows = await self._fetch(query, [*params, limit])
        return [
            TransactionRow(
                occurred_at=cast(datetime, r[0]),
                kind=cast(TransactionKind, r[1]),
                amount=cast(Decimal, r[2]),
                currency=cast(Currency, r[3]),
                category=cast(str, r[4]),
                description=cast(str | None, r[5]),
            )
            for r in rows
        ]
