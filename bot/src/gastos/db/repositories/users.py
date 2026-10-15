"""Repositorio de usuarios con SQL explícito."""

from datetime import datetime
from typing import Any, cast
from uuid import UUID

from psycopg import sql
from psycopg_pool import AsyncConnectionPool

from gastos.domain.currency import Currency, VesRateSource
from gastos.domain.user import User

_COLUMNS = sql.SQL(
    "id, telegram_id, display_name, timezone, default_currency, ves_rate_source, onboarded_at"
)
# Columnas que acepta `_update`; evita componer SQL con nombres arbitrarios.
_UPDATABLE = frozenset({"default_currency", "ves_rate_source"})


def _to_user(row: tuple[Any, ...]) -> User:
    return User(
        id=cast(UUID, row[0]),
        telegram_id=cast(int, row[1]),
        display_name=cast(str | None, row[2]),
        timezone=cast(str, row[3]),
        default_currency=cast(Currency, row[4]),
        ves_rate_source=cast(VesRateSource, row[5]),
        onboarded_at=cast(datetime | None, row[6]),
    )


class UserRepository:
    def __init__(self, pool: AsyncConnectionPool) -> None:
        self._pool = pool

    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        query = sql.SQL("select {} from users where telegram_id = %s").format(_COLUMNS)
        async with self._pool.connection() as conn:
            cur = await conn.execute(query, (telegram_id,))
            row = await cur.fetchone()
        return _to_user(row) if row else None

    async def create(self, telegram_id: int, display_name: str | None) -> User:
        """Crea el usuario (el trigger le crea sus cuentas); si ya existe, lo devuelve."""
        query = sql.SQL(
            "insert into users (telegram_id, display_name) values (%s, %s) "
            "on conflict (telegram_id) do nothing returning {}"
        ).format(_COLUMNS)
        async with self._pool.connection() as conn:
            cur = await conn.execute(query, (telegram_id, display_name))
            row = await cur.fetchone()
        if row:
            return _to_user(row)
        # Otro update del mismo usuario lo creó en paralelo.
        existing = await self.get_by_telegram_id(telegram_id)
        if existing is None:
            raise LookupError(f"no se pudo crear ni leer el usuario {telegram_id}")
        return existing

    async def set_default_currency(self, user_id: UUID, currency: Currency) -> User:
        return await self._update(user_id, "default_currency", currency)

    async def set_ves_rate_source(self, user_id: UUID, source: VesRateSource) -> User:
        return await self._update(user_id, "ves_rate_source", source)

    async def complete_onboarding(self, user_id: UUID, timezone: str) -> User:
        """Guarda la zona horaria y marca el onboarding (conserva la primera fecha)."""
        query = sql.SQL(
            "update users set timezone = %s, onboarded_at = coalesce(onboarded_at, now()) "
            "where id = %s returning {}"
        ).format(_COLUMNS)
        return await self._fetch_one(query, (timezone, user_id))

    async def _update(self, user_id: UUID, column: str, value: str) -> User:
        if column not in _UPDATABLE:
            raise ValueError(f"columna no actualizable: {column}")
        query = sql.SQL("update users set {} = %s where id = %s returning {}").format(
            sql.Identifier(column), _COLUMNS
        )
        return await self._fetch_one(query, (value, user_id))

    async def _fetch_one(self, query: sql.Composed, params: tuple[Any, ...]) -> User:
        async with self._pool.connection() as conn:
            cur = await conn.execute(query, params)
            row = await cur.fetchone()
        if row is None:
            raise LookupError("usuario no encontrado")
        return _to_user(row)
