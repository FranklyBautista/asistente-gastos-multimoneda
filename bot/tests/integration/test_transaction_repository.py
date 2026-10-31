"""Repositorio de movimientos contra el Postgres de Supabase local (`.\\tasks.ps1 db-up`)."""

import os
import random
from collections.abc import AsyncIterator
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal

import psycopg
import pytest
from psycopg_pool import AsyncConnectionPool

from gastos.db.pool import create_pool
from gastos.db.repositories.transactions import TransactionRepository
from gastos.db.repositories.users import UserRepository
from gastos.domain.conversion import UsdSnapshot
from gastos.domain.transaction import NewTransaction
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


async def new_user(pool: AsyncConnectionPool) -> User:
    return await UserRepository(pool).create(random.randint(900000000000, 999999999999), None)


async def new_items(repo: TransactionRepository, user: User, raw: str) -> list[NewTransaction]:
    accounts = {a.currency: a for a in await repo.accounts(user.id)}
    categories = {(c.name, c.kind): c for c in await repo.categories(user.id)}
    base = NewTransaction(
        account=accounts["VES"],
        kind="expense",
        amount=Decimal(70),
        category=categories[("transporte", "expense")],
        description="pasaje",
        snapshot=UsdSnapshot(Decimal("0.001"), "parallel", Decimal("0.07")),
        occurred_at=None,
        raw_text=raw,
        parse_confidence=0.95,
    )
    usd = replace(
        base,
        account=accounts["USD"],
        amount=Decimal(15),
        category=categories[("comida", "expense")],
        description="almuerzo",
        snapshot=UsdSnapshot(Decimal(1), "pivot", Decimal(15)),
        occurred_at=datetime(2026, 10, 30, 16, tzinfo=UTC),
    )
    return [base, usd]


async def test_cuentas_y_categorias_del_usuario(pool: AsyncConnectionPool) -> None:
    repo = TransactionRepository(pool)
    user = await new_user(pool)
    assert {a.currency for a in await repo.accounts(user.id)} == {"VES", "COP", "USD", "USDT"}
    names = {(c.name, c.kind) for c in await repo.categories(user.id)}
    assert {("otros", "expense"), ("otros ingresos", "income")} <= names


async def test_guardar_varios_mueve_los_saldos(pool: AsyncConnectionPool) -> None:
    repo = TransactionRepository(pool)
    user = await new_user(pool)
    saved = await repo.insert_many(user.id, await new_items(repo, user, "pasaje 70 bs y ..."))
    assert [s.amount for s in saved] == [Decimal(70), Decimal(15)]
    assert saved[1].occurred_at == datetime(2026, 10, 30, 16, tzinfo=UTC)
    async with pool.connection() as conn:
        cur = await conn.execute(
            "select currency, balance from account_balances where user_id = %s "
            "and currency in ('VES', 'USD') order by currency",
            (user.id,),
        )
        assert await cur.fetchall() == [("USD", Decimal(-15)), ("VES", Decimal(-70))]


async def test_deshacer_borra_solo_el_lote_y_solo_del_dueno(pool: AsyncConnectionPool) -> None:
    repo = TransactionRepository(pool)
    user = await new_user(pool)
    first = await repo.insert_many(user.id, await new_items(repo, user, "primero"))
    second = await repo.insert_many(user.id, await new_items(repo, user, "segundo"))

    intruder = await new_user(pool)
    assert await repo.undo_batch(intruder.id, first[0].id) == 0
    assert await repo.undo_batch(user.id, first[1].id) == 2
    assert await repo.undo_batch(user.id, first[1].id) == 0
    async with pool.connection() as conn:
        cur = await conn.execute(
            "select id from transactions where user_id = %s and deleted_at is null", (user.id,)
        )
        assert {r[0] for r in await cur.fetchall()} == {s.id for s in second}


async def test_moneda_de_otra_cuenta_la_rechaza_la_base(pool: AsyncConnectionPool) -> None:
    repo = TransactionRepository(pool)
    user = await new_user(pool)
    [ves, usd] = await new_items(repo, user, "x")
    wrong = replace(ves, account=replace(usd.account, currency="VES"))
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        await repo.insert_many(user.id, [ves, wrong])
    # La transacción se revirtió completa: tampoco quedó el primero.
    async with pool.connection() as conn:
        cur = await conn.execute("select count(*) from transactions where user_id = %s", (user.id,))
        assert await cur.fetchone() == (0,)
