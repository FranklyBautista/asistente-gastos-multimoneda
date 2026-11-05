"""Updates de Telegram ya recibidos: evita procesar dos veces el mismo (ADR 0011)."""

from datetime import datetime

from psycopg_pool import AsyncConnectionPool


class UpdateRepository:
    def __init__(self, pool: AsyncConnectionPool) -> None:
        self._pool = pool

    async def claim(self, bot_id: int, update_id: int) -> bool:
        """Reserva el update; False si ya se había recibido."""
        async with self._pool.connection() as conn:
            cur = await conn.execute(
                "insert into processed_updates (bot_id, update_id) values (%s, %s) "
                "on conflict do nothing returning update_id",
                (bot_id, update_id),
            )
            return await cur.fetchone() is not None

    async def purge_before(self, cutoff: datetime) -> int:
        """Borra los registros anteriores a `cutoff` y devuelve cuántos borró."""
        async with self._pool.connection() as conn:
            cur = await conn.execute(
                "delete from processed_updates where received_at < %s", (cutoff,)
            )
            return cur.rowcount
