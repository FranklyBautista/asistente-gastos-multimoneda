"""Correcciones contra el Postgres de Supabase local (`.\\tasks.ps1 db-up`)."""

import os
import random
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from decimal import Decimal

import psycopg
import pytest
from psycopg_pool import AsyncConnectionPool

from gastos.db.pool import create_pool
from gastos.db.repositories.corrections import CorrectionRepository
from gastos.db.repositories.reports import ReportRepository
from gastos.db.repositories.transactions import TransactionRepository
from gastos.db.repositories.users import UserRepository
from gastos.domain.conversion import UsdSnapshot
from gastos.domain.correction import CorrectedValues, CorrectionExample, changes_between
from gastos.domain.currency import Currency
from gastos.domain.transaction import NewTransaction
from gastos.domain.user import User

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://postgres:postgres@127.0.0.1:55322/postgres"
)
D = Decimal


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


async def save(
    pool: AsyncConnectionPool, user: User, raw_text: str, *items: tuple[str, int, Currency]
) -> None:
    repo = TransactionRepository(pool)
    accounts = {a.currency: a for a in await repo.accounts(user.id)}
    categories = {c.name: c for c in await repo.categories(user.id)}
    await repo.insert_many(
        user.id,
        [
            NewTransaction(
                account=accounts[currency],
                kind="expense",
                amount=D(amount),
                category=categories["comida"],
                description=description,
                snapshot=UsdSnapshot(D(1), "pivot", D(amount)),
                occurred_at=datetime(2026, 11, 1, tzinfo=UTC),
                raw_text=raw_text,
                parse_confidence=0.9,
            )
            for description, amount, currency in items
        ],
    )


async def test_el_ultimo_mensaje_con_todos_sus_movimientos(pool: AsyncConnectionPool) -> None:
    user = await new_user(pool)
    repo = CorrectionRepository(pool)
    assert await repo.last_batch(user.id) == []
    await save(pool, user, "pan 2", ("pan", 2, "USD"))
    await save(pool, user, "almuerzo 15 y café 3", ("almuerzo", 15, "USD"), ("café", 3, "USD"))
    batch = await repo.last_batch(user.id)
    assert [(t.description, t.amount, t.category.name) for t in batch] == [
        ("almuerzo", D(15), "comida"),
        ("café", D(3), "comida"),
    ]


async def test_cambiar_de_moneda_mueve_el_saldo_y_queda_registrado(
    pool: AsyncConnectionPool,
) -> None:
    user = await new_user(pool)
    await save(pool, user, "taxi 20 mil", ("taxi", 20000, "USD"))
    tx_repo = TransactionRepository(pool)
    repo = CorrectionRepository(pool)
    [target] = await repo.last_batch(user.id)
    cop = next(a for a in await tx_repo.accounts(user.id) if a.currency == "COP")
    transport = next(c for c in await tx_repo.categories(user.id) if c.name == "transporte")
    values = CorrectedValues(
        "expense", D(20000), cop, transport, UsdSnapshot(D("0.00025"), "fx", D(5))
    )
    changes = changes_between(target, values)
    assert await repo.apply(user.id, target.id, values, changes, "eran pesos, de transporte")

    balances = {
        b.currency: b.balance for b in await ReportRepository(pool).account_balances(user.id)
    }
    assert (balances["USD"], balances["COP"]) == (D(0), D(-20000))
    [after] = await repo.last_batch(user.id)
    assert (after.currency, after.category.name, after.snapshot.amount_usd) == (
        "COP",
        "transporte",
        D(5),
    )
    # Las dos se guardaron en la misma transacción: el orden entre ellas no importa.
    assert set(await repo.recent_examples(user.id, 10)) == {
        CorrectionExample("taxi 20 mil", "category", "transporte"),
        CorrectionExample("taxi 20 mil", "currency", "COP"),
    }


async def test_movimiento_deshecho_o_de_otro_usuario_no_se_corrige(
    pool: AsyncConnectionPool,
) -> None:
    user, other = await new_user(pool), await new_user(pool)
    await save(pool, user, "pan 2", ("pan", 2, "USD"))
    repo = CorrectionRepository(pool)
    [target] = await repo.last_batch(user.id)
    values = CorrectedValues("expense", D(3), target.account, target.category, target.snapshot)
    changes = changes_between(target, values)
    assert not await repo.apply(other.id, target.id, values, changes, "eran 3")
    await TransactionRepository(pool).undo_batch(user.id, target.id)
    assert not await repo.apply(user.id, target.id, values, changes, "eran 3")
    assert await repo.recent_examples(user.id, 10) == []


async def test_ejemplos_solo_la_ultima_correccion_de_cada_campo(pool: AsyncConnectionPool) -> None:
    user = await new_user(pool)
    await save(pool, user, "netflix 8", ("netflix", 8, "USD"))
    tx_repo = TransactionRepository(pool)
    repo = CorrectionRepository(pool)
    categories = {c.name: c for c in await tx_repo.categories(user.id)}
    for name in ("servicios", "ocio"):
        [target] = await repo.last_batch(user.id)
        values = CorrectedValues(
            "expense", target.amount, target.account, categories[name], target.snapshot
        )
        assert await repo.apply(
            user.id, target.id, values, changes_between(target, values), f"eso fue {name}"
        )
    assert await repo.recent_examples(user.id, 10) == [
        CorrectionExample("netflix 8", "category", "ocio")
    ]
