"""Cambios entre monedas contra el Postgres de Supabase local (`.\\tasks.ps1 db-up`)."""

import os
import random
from collections.abc import AsyncIterator
from dataclasses import replace
from decimal import Decimal
from uuid import UUID

import psycopg
import pytest
from psycopg_pool import AsyncConnectionPool

from gastos.db.pool import create_pool
from gastos.db.repositories.exchanges import ExchangeRepository
from gastos.db.repositories.transactions import TransactionRepository
from gastos.db.repositories.users import UserRepository
from gastos.domain.account import Account
from gastos.domain.exchange import ExchangeAmounts, NewExchange
from gastos.domain.user import User

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
    await pool.close()


async def new_user(pool: AsyncConnectionPool) -> tuple[User, dict[str, Account]]:
    user = await UserRepository(pool).create(random.randint(900000000000, 999999999999), None)
    accounts = await TransactionRepository(pool).accounts(user.id)
    return user, {a.currency: a for a in accounts}


def usdt_to_ves(accounts: dict[str, Account]) -> NewExchange:
    return NewExchange(
        from_account=accounts["USDT"],
        to_account=accounts["VES"],
        amounts=ExchangeAmounts(Decimal(50), Decimal(49250), Decimal(985)),
        reference_rate=Decimal(999),
        occurred_at=None,
        raw_text="cambié 50 usdt a bs a 985",
    )


async def balances(pool: AsyncConnectionPool, user_id: UUID) -> dict[str, Decimal]:
    async with pool.connection() as conn:
        cur = await conn.execute(
            "select currency, balance from account_balances where user_id = %s", (user_id,)
        )
        return {r[0]: r[1] for r in await cur.fetchall()}


async def test_cambio_de_usdt_a_bs_mueve_los_dos_saldos(pool: AsyncConnectionPool) -> None:
    repo = ExchangeRepository(pool)
    user, accounts = await new_user(pool)
    saved = await repo.insert(user.id, usdt_to_ves(accounts))
    assert (saved.from_currency, saved.to_currency) == ("USDT", "VES")
    assert saved.occurred_at is not None
    assert await balances(pool, user.id) == {
        "USDT": Decimal(-50),
        "VES": Decimal(49250),
        "COP": Decimal(0),
        "USD": Decimal(0),
    }
    async with pool.connection() as conn:
        cur = await conn.execute(
            "select effective_rate, reference_rate, raw_text from exchanges where id = %s",
            (saved.id,),
        )
        assert await cur.fetchone() == (Decimal(985), Decimal(999), "cambié 50 usdt a bs a 985")


async def test_deshacer_devuelve_los_saldos_y_solo_lo_hace_el_dueno(
    pool: AsyncConnectionPool,
) -> None:
    repo = ExchangeRepository(pool)
    user, accounts = await new_user(pool)
    saved = await repo.insert(user.id, usdt_to_ves(accounts))
    intruder, _ = await new_user(pool)
    assert await repo.undo(intruder.id, saved.id) == 0
    assert await repo.undo(user.id, saved.id) == 1
    assert await repo.undo(user.id, saved.id) == 0
    assert set((await balances(pool, user.id)).values()) == {Decimal(0)}


async def test_la_base_rechaza_cuentas_de_otro_usuario(pool: AsyncConnectionPool) -> None:
    repo = ExchangeRepository(pool)
    user, accounts = await new_user(pool)
    _, other_accounts = await new_user(pool)
    stolen = replace(usdt_to_ves(accounts), to_account=other_accounts["VES"])
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        await repo.insert(user.id, stolen)
