"""Updates recibidos contra el Postgres de Supabase local (`.\\tasks.ps1 db-up`)."""

import os
import random
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import psycopg
import pytest
from psycopg_pool import AsyncConnectionPool

from gastos.db.pool import create_pool
from gastos.db.repositories.updates import UpdateRepository

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://postgres:postgres@127.0.0.1:55322/postgres"
)
# Ids de bot ficticios (los reales son mucho menores) para no chocar con datos de desarrollo.
TEST_BOTS = (990000000001, 990000000002)


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
        await conn.execute(
            "delete from processed_updates where bot_id = any(%s)", (list(TEST_BOTS),)
        )
    await pool.close()


async def test_reserva_cada_update_una_sola_vez_por_bot(pool: AsyncConnectionPool) -> None:
    repo = UpdateRepository(pool)
    update_id = random.randint(1, 10**9)
    assert await repo.claim(TEST_BOTS[0], update_id)
    assert not await repo.claim(TEST_BOTS[0], update_id)
    assert await repo.claim(TEST_BOTS[1], update_id)  # otro bot, otra numeración
    assert await repo.claim(TEST_BOTS[0], update_id + 1)


async def test_purga_solo_lo_viejo(pool: AsyncConnectionPool) -> None:
    repo = UpdateRepository(pool)
    async with pool.connection() as conn:
        await conn.execute(
            "insert into processed_updates (bot_id, update_id, received_at) values "
            "(%s, 1, now() - interval '3 days'), (%s, 2, now())",
            (TEST_BOTS[0], TEST_BOTS[0]),
        )
    assert await repo.purge_before(datetime.now(UTC) - timedelta(days=2)) >= 1
    assert await repo.claim(TEST_BOTS[0], 1)  # se borró: vuelve a poder reservarse
    assert not await repo.claim(TEST_BOTS[0], 2)  # el reciente sigue ahí
