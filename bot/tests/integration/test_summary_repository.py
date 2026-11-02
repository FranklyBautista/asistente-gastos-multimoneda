"""Resúmenes enviados contra el Postgres de Supabase local (`.\\tasks.ps1 db-up`)."""

import os
import random
from collections.abc import AsyncIterator
from datetime import date

import psycopg
import pytest
from psycopg_pool import AsyncConnectionPool

from gastos.db.pool import create_pool
from gastos.db.repositories.summaries import SummaryRepository
from gastos.db.repositories.users import UserRepository

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://postgres:postgres@127.0.0.1:55322/postgres"
)
MONDAY = date(2026, 10, 26)


@pytest.fixture
async def pool() -> AsyncIterator[AsyncConnectionPool]:
    try:
        async with await psycopg.AsyncConnection.connect(DATABASE_URL, connect_timeout=2):
            pass
    except psycopg.OperationalError:
        if os.environ.get("REQUIRE_DB"):  # en el CI, saltarse las pruebas sería un falso verde
            raise
        pytest.skip("Supabase local no está levantado")
    pool = create_pool(DATABASE_URL)
    await pool.open()
    yield pool
    async with pool.connection() as conn:
        await conn.execute("delete from users where telegram_id >= 900000000000")
    await pool.close()


async def test_reserva_una_sola_vez_por_semana_y_usuario(pool: AsyncConnectionPool) -> None:
    users = UserRepository(pool)
    ana = await users.create(random.randint(900000000000, 999999999999), None)
    luis = await users.create(random.randint(900000000000, 999999999999), None)
    repo = SummaryRepository(pool)
    assert await repo.claim(ana.id, MONDAY)
    assert not await repo.claim(ana.id, MONDAY)
    assert await repo.claim(luis.id, MONDAY)  # cada usuario tiene su propia reserva
    assert await repo.claim(ana.id, date(2026, 11, 2))  # y cada semana también


async def test_liberar_permite_reintentar(pool: AsyncConnectionPool) -> None:
    ana = await UserRepository(pool).create(random.randint(900000000000, 999999999999), None)
    repo = SummaryRepository(pool)
    assert await repo.claim(ana.id, MONDAY)
    await repo.release(ana.id, MONDAY)
    assert await repo.claim(ana.id, MONDAY)
