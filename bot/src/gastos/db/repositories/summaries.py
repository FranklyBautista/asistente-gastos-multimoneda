"""Registro de resúmenes semanales enviados: evita mandar dos veces el de la misma semana."""

from datetime import date
from uuid import UUID

from psycopg_pool import AsyncConnectionPool


class SummaryRepository:
    def __init__(self, pool: AsyncConnectionPool) -> None:
        self._pool = pool

    async def claim(self, user_id: UUID, week_start: date) -> bool:
        """Reserva el envío de esa semana; False si ya estaba reservado (o enviado)."""
        async with self._pool.connection() as conn:
            cur = await conn.execute(
                "insert into weekly_summaries (user_id, week_start) values (%s, %s) "
                "on conflict do nothing returning user_id",
                (user_id, week_start),
            )
            return await cur.fetchone() is not None

    async def release(self, user_id: UUID, week_start: date) -> None:
        """Libera la reserva si el envío falló, para reintentarlo en la próxima corrida."""
        async with self._pool.connection() as conn:
            await conn.execute(
                "delete from weekly_summaries where user_id = %s and week_start = %s",
                (user_id, week_start),
            )
