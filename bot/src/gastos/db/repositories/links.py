"""Códigos de vinculación con la web y estado de la vinculación (ADR 0012)."""

from datetime import datetime
from uuid import UUID

from psycopg_pool import AsyncConnectionPool


class LinkRepository:
    def __init__(self, pool: AsyncConnectionPool) -> None:
        self._pool = pool

    async def is_linked(self, user_id: UUID) -> bool:
        async with self._pool.connection() as conn:
            cur = await conn.execute(
                "select auth_user_id is not null from users where id = %s", (user_id,)
            )
            row = await cur.fetchone()
        return bool(row and row[0])

    async def issue(self, user_id: UUID, code: str, expires_at: datetime) -> bool:
        """Guarda el código y anula los anteriores sin usar; False si el código ya existía."""
        async with self._pool.connection() as conn, conn.transaction():
            await conn.execute(
                "delete from link_codes where user_id = %s and used_at is null", (user_id,)
            )
            cur = await conn.execute(
                "insert into link_codes (code, user_id, expires_at) values (%s, %s, %s) "
                "on conflict do nothing returning code",
                (code, user_id, expires_at),
            )
            return await cur.fetchone() is not None
