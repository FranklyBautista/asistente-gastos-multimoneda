"""Códigos de vinculación contra el Postgres de Supabase local (`.\\tasks.ps1 db-up`)."""

import os
import random
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import psycopg
import pytest
from psycopg_pool import AsyncConnectionPool

from gastos.db.pool import create_pool
from gastos.db.repositories.links import LinkRepository
from gastos.db.repositories.users import UserRepository
from gastos.domain.linking import new_code

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://postgres:postgres@127.0.0.1:55322/postgres"
)


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
        await conn.execute("delete from auth.users where email like '%@test.invalid'")
    await pool.close()


async def test_un_codigo_nuevo_anula_los_anteriores_sin_usar(pool: AsyncConnectionPool) -> None:
    user = await UserRepository(pool).create(random.randint(900000000000, 999999999999), None)
    repo = LinkRepository(pool)
    expires = datetime.now(UTC) + timedelta(minutes=10)
    first, second = new_code(), new_code()
    assert await repo.issue(user.id, first, expires)
    assert await repo.issue(user.id, second, expires)
    async with pool.connection() as conn:
        cur = await conn.execute("select code from link_codes where user_id = %s", (user.id,))
        assert [r[0] for r in await cur.fetchall()] == [second]


async def test_un_codigo_repetido_no_se_guarda(pool: AsyncConnectionPool) -> None:
    users = UserRepository(pool)
    ana = await users.create(random.randint(900000000000, 999999999999), None)
    beto = await users.create(random.randint(900000000000, 999999999999), None)
    repo = LinkRepository(pool)
    code = new_code()
    expires = datetime.now(UTC) + timedelta(minutes=10)
    assert await repo.issue(ana.id, code, expires)
    assert not await repo.issue(beto.id, code, expires)


async def test_sabe_si_el_usuario_ya_tiene_cuenta_web(pool: AsyncConnectionPool) -> None:
    user = await UserRepository(pool).create(random.randint(900000000000, 999999999999), None)
    repo = LinkRepository(pool)
    assert not await repo.is_linked(user.id)
    auth_id = uuid4()
    async with pool.connection() as conn:
        await conn.execute(
            "insert into auth.users (id, email) values (%s, %s)",
            (auth_id, f"{auth_id}@test.invalid"),
        )
        await conn.execute("update users set auth_user_id = %s where id = %s", (auth_id, user.id))
    assert await repo.is_linked(user.id)
