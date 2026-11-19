"""Topes, primer movimiento y preferencia de contexto contra Supabase local (`db-up`)."""

import os
import random
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from decimal import Decimal

import psycopg
import pytest
from psycopg_pool import AsyncConnectionPool

from gastos.db.pool import create_pool
from gastos.db.repositories.budgets import BudgetRepository
from gastos.db.repositories.reports import ReportRepository
from gastos.db.repositories.transactions import TransactionRepository
from gastos.db.repositories.users import UserRepository
from gastos.domain.account import Category
from gastos.domain.conversion import UsdSnapshot
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
        if os.environ.get("REQUIRE_DB"):
            raise
        pytest.skip("Supabase local no está levantado")
    pool = create_pool(DATABASE_URL)
    await pool.open()
    yield pool
    async with pool.connection() as conn:
        await conn.execute("delete from users where telegram_id >= 900000000000")
    await pool.close()


async def new_user(pool: AsyncConnectionPool) -> tuple[User, dict[str, Category]]:
    user = await UserRepository(pool).create(random.randint(900000000000, 999999999999), None)
    categories = {c.name: c for c in await TransactionRepository(pool).categories(user.id)}
    return user, categories


async def test_fijar_reemplazar_y_deshacer_un_tope(pool: AsyncConnectionPool) -> None:
    user, categories = await new_user(pool)
    repo = BudgetRepository(pool)
    food = categories["comida"]

    first, replaced = await repo.set(user.id, food, D(100), "tope comida 100")
    assert replaced is None
    assert [b.limit_usd for b in await repo.active(user.id)] == [D(100)]

    second, replaced = await repo.set(user.id, food, D(150), "mejor 150")
    assert replaced == first
    assert [(b.id, b.limit_usd) for b in await repo.active(user.id)] == [(second.id, D(150))]

    # Deshacer el segundo restaura el primero; deshacerlo otra vez no hace nada.
    assert await repo.undo(user.id, second.id) is True
    assert [b.id for b in await repo.active(user.id)] == [first.id]
    assert await repo.undo(user.id, second.id) is False


async def test_quitar_un_tope_y_aislamiento(pool: AsyncConnectionPool) -> None:
    user, categories = await new_user(pool)
    other, _ = await new_user(pool)
    repo = BudgetRepository(pool)
    budget, _ = await repo.set(user.id, categories["ocio"], D(40), None)
    await repo.set(user.id, categories["comida"], D(90), None)

    assert await repo.undo(other.id, budget.id) is False  # no es de ese usuario
    assert await repo.active(other.id) == []
    removed = await repo.remove(user.id, categories["ocio"])
    assert removed == budget
    assert await repo.remove(user.id, categories["ocio"]) is None
    assert [b.category for b in await repo.active(user.id)] == ["comida"]


async def test_primer_movimiento_y_preferencia_de_contexto(pool: AsyncConnectionPool) -> None:
    user, categories = await new_user(pool)
    reports = ReportRepository(pool)
    assert await reports.first_movement_at(user.id) is None

    transactions = TransactionRepository(pool)
    usd = next(a for a in await transactions.accounts(user.id) if a.currency == "USD")
    when = datetime(2026, 10, 3, 15, tzinfo=UTC)
    item = NewTransaction(
        account=usd,
        kind="expense",
        amount=D(5),
        category=categories["comida"],
        description="café",
        snapshot=UsdSnapshot(D(1), "pivot", D(5)),
        occurred_at=when,
        raw_text="café 5 dólares",
        parse_confidence=0.9,
    )
    await transactions.insert_many(user.id, [item])
    assert await reports.first_movement_at(user.id) == when

    users = UserRepository(pool)
    assert user.context_replies is True
    updated = await users.set_context_replies(user.id, False)
    assert updated.context_replies is False
    fetched = await users.get_by_telegram_id(user.telegram_id)
    assert fetched is not None and fetched.context_replies is False
