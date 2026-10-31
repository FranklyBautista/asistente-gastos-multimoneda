"""Repositorio de tasas de cambio con SQL explícito.

Las tasas son datos globales (no pertenecen a ningún usuario), así que aquí no se filtra
por user_id. Cada refresco agrega filas: la tabla es también el historial.
"""

from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal
from typing import Any, cast

from psycopg_pool import AsyncConnectionPool

from gastos.domain.conversion import Rate
from gastos.domain.currency import QuotedCurrency, RateSource


def _to_rate(row: tuple[Any, ...]) -> Rate:
    return Rate(
        currency=cast(QuotedCurrency, row[0]),
        source=cast(RateSource, row[1]),
        usd_per_unit=cast(Decimal, row[2]),
        fetched_at=cast(datetime, row[3]),
    )


class RateRepository:
    def __init__(self, pool: AsyncConnectionPool) -> None:
        self._pool = pool

    async def save(self, rates: Sequence[Rate]) -> None:
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.executemany(
                "insert into exchange_rates (currency, source, usd_per_unit, fetched_at) "
                "values (%s, %s, %s, %s)",
                [(r.currency, r.source, r.usd_per_unit, r.fetched_at) for r in rates],
            )

    async def latest(self, currency: QuotedCurrency, source: RateSource) -> Rate | None:
        """La tasa más reciente de esa moneda y fuente (usa el índice por fetched_at)."""
        async with self._pool.connection() as conn:
            cur = await conn.execute(
                "select currency, source, usd_per_unit, fetched_at from exchange_rates "
                "where currency = %s and source = %s order by fetched_at desc limit 1",
                (currency, source),
            )
            row = await cur.fetchone()
        return _to_rate(row) if row else None
