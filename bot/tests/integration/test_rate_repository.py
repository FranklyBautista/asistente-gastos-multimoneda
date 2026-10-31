"""Repositorio de tasas contra el Postgres de Supabase local (`.\\tasks.ps1 db-up`).

Las filas de prueba van fechadas en el año 2999 para que sean siempre las más recientes y
se puedan borrar sin tocar las tasas reales que haya guardado el bot.
"""

import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import psycopg
import pytest

from gastos.db.pool import create_pool
from gastos.db.repositories.rates import RateRepository
from gastos.domain.conversion import Rate

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://postgres:postgres@127.0.0.1:55322/postgres"
)
FUTURE = datetime(2999, 1, 1, tzinfo=UTC)


@pytest.fixture
async def repo() -> AsyncIterator[RateRepository]:
    try:
        async with await psycopg.AsyncConnection.connect(DATABASE_URL, connect_timeout=2):
            pass
    except psycopg.OperationalError:
        if os.environ.get("REQUIRE_DB"):  # en el CI, saltarse las pruebas sería un falso verde
            raise
        pytest.skip("Supabase local no está levantado")
    pool = create_pool(DATABASE_URL)
    await pool.open()
    yield RateRepository(pool)
    async with pool.connection() as conn:
        await conn.execute("delete from exchange_rates where fetched_at >= %s", (FUTURE,))
    await pool.close()


async def test_guarda_y_devuelve_la_mas_reciente_sin_perder_precision(
    repo: RateRepository,
) -> None:
    older = Rate("VES", "p2p", Decimal("0.0009930435"), FUTURE)
    newer = Rate("VES", "p2p", Decimal("0.0009986774"), FUTURE + timedelta(hours=1))
    other_source = Rate("VES", "bcv", Decimal("0.0011270120"), FUTURE + timedelta(hours=2))
    await repo.save([older, newer, other_source])
    assert await repo.latest("VES", "p2p") == newer
    assert await repo.latest("VES", "bcv") == other_source


async def test_la_base_rechaza_una_tasa_que_no_es_positiva(repo: RateRepository) -> None:
    rate = Rate("COP", "fx", Decimal("0.0003181239"), FUTURE)
    object.__setattr__(rate, "usd_per_unit", Decimal(0))  # salta la validación del dominio
    with pytest.raises(psycopg.errors.CheckViolation):
        await repo.save([rate])
