"""Repositorio de usuarios contra el Postgres de Supabase local (`.\\tasks.ps1 db-up`)."""

import os
import random
from collections.abc import AsyncIterator

import psycopg
import pytest

from gastos.db.pool import create_pool
from gastos.db.repositories.users import UserRepository

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://postgres:postgres@127.0.0.1:55322/postgres"
)


@pytest.fixture
async def repo() -> AsyncIterator[UserRepository]:
    try:
        async with await psycopg.AsyncConnection.connect(DATABASE_URL, connect_timeout=2):
            pass
    except psycopg.OperationalError:
        if os.environ.get("REQUIRE_DB"):  # en el CI, saltarse las pruebas sería un falso verde
            raise
        pytest.skip("Supabase local no está levantado")
    pool = create_pool(DATABASE_URL)
    await pool.open()
    yield UserRepository(pool)
    async with pool.connection() as conn:
        await conn.execute("delete from users where telegram_id >= 900000000000")
    await pool.close()


def _telegram_id() -> int:
    return random.randint(900000000000, 999999999999)


async def test_crear_es_idempotente_y_da_cuentas(repo: UserRepository) -> None:
    telegram_id = _telegram_id()
    created = await repo.create(telegram_id, "Ana")
    again = await repo.create(telegram_id, "Otro nombre")
    assert again.id == created.id
    assert created.default_currency == "USD"
    assert not created.is_onboarded
    assert await repo.get_by_telegram_id(telegram_id) == created


async def test_onboarding_guarda_preferencias(repo: UserRepository) -> None:
    user = await repo.create(_telegram_id(), None)
    await repo.set_default_currency(user.id, "VES")
    await repo.set_ves_rate_source(user.id, "bcv")
    done = await repo.complete_onboarding(user.id, "America/Bogota")
    assert (done.default_currency, done.ves_rate_source, done.timezone) == (
        "VES",
        "bcv",
        "America/Bogota",
    )
    assert done.onboarded_at is not None
    # Repetir el onboarding conserva la primera fecha.
    redo = await repo.complete_onboarding(user.id, "America/Caracas")
    assert redo.onboarded_at == done.onboarded_at
