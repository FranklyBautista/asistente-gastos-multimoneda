"""Deudas contra el Postgres de Supabase local (`.\\tasks.ps1 db-up`)."""

import os
import random
from collections.abc import AsyncIterator
from decimal import Decimal
from uuid import UUID

import psycopg
import pytest
from psycopg_pool import AsyncConnectionPool

from gastos.db.pool import create_pool
from gastos.db.repositories.corrections import CorrectionRepository
from gastos.db.repositories.debts import DebtRepository
from gastos.db.repositories.transactions import TransactionRepository
from gastos.db.repositories.users import UserRepository
from gastos.domain.account import Account, Category
from gastos.domain.conversion import UsdSnapshot
from gastos.domain.debt import Debt, NewDebt
from gastos.domain.errors import DebtChanged
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
        if os.environ.get("REQUIRE_DB"):
            raise
        pytest.skip("Supabase local no está levantado")
    pool = create_pool(DATABASE_URL)
    await pool.open()
    yield pool
    async with pool.connection() as conn:
        await conn.execute("delete from users where telegram_id >= 900000000000")
    await pool.close()


async def new_user(
    pool: AsyncConnectionPool,
) -> tuple[User, dict[str, Account], dict[str, Category]]:
    user = await UserRepository(pool).create(random.randint(900000000000, 999999999999), None)
    repo = TransactionRepository(pool)
    accounts = {a.currency: a for a in await repo.accounts(user.id)}
    categories = {c.name: c for c in await repo.categories(user.id)}
    return user, accounts, categories


def new_debt(category: Category | None = None) -> NewDebt:
    return NewDebt(
        direction="i_owe",
        counterparty="Míguel",
        currency="USD",
        amount=Decimal(20),
        category=category,
        description="almuerzo",
        snapshot=UsdSnapshot(Decimal(1), "pivot", Decimal(20)),
        raw_text="le debo 20 dólares a míguel",
    )


def movement(account: Account, category: Category, amount: str) -> NewTransaction:
    return NewTransaction(
        account=account,
        kind="expense",
        amount=Decimal(amount),
        category=category,
        description="deuda con Míguel",
        snapshot=UsdSnapshot(Decimal(1), "pivot", Decimal(amount)),
        occurred_at=None,
        raw_text="le pagué a miguel",
        parse_confidence=1.0,
    )


async def usd_balance(pool: AsyncConnectionPool, user_id: UUID) -> Decimal:
    async with pool.connection() as conn:
        cur = await conn.execute(
            "select balance from account_balances where user_id = %s and currency = 'USD'",
            (user_id,),
        )
        row = await cur.fetchone()
    assert row is not None
    return row[0]


async def test_anotar_y_listar(pool: AsyncConnectionPool) -> None:
    repo = DebtRepository(pool)
    user, _, categories = await new_user(pool)
    saved = await repo.insert(user.id, new_debt(categories["comida"]))
    [listed] = await repo.list(user.id)
    assert listed == saved
    assert (listed.category, listed.status, listed.remaining) == ("comida", "open", Decimal(20))
    assert await repo.list(user.id, direction="owed_to_me") == []
    assert await usd_balance(pool, user.id) == 0  # anotar una deuda no mueve saldos


async def test_pagar_con_dinero_crea_el_gasto_y_mueve_el_saldo(pool: AsyncConnectionPool) -> None:
    repo = DebtRepository(pool)
    user, accounts, categories = await new_user(pool)
    debt = await repo.insert(user.id, new_debt())
    payment_id, saved, after = await repo.pay(
        user.id, debt, Decimal(5), movement(accounts["USD"], categories["pago de deudas"], "5"), "x"
    )
    assert saved is not None and saved.category == "pago de deudas"
    assert (after.status, after.remaining) == ("partial", Decimal(15))
    assert await usd_balance(pool, user.id) == Decimal(-5)

    # Deshacer el pago borra también el gasto, y la deuda vuelve a estar abierta.
    assert await repo.undo_payment(user.id, payment_id) == 1
    assert await repo.undo_payment(user.id, payment_id) == 0
    assert await usd_balance(pool, user.id) == 0
    current = await repo.get(user.id, debt.id)
    assert current is not None and current.status == "open"


async def test_un_pago_de_mas_no_deja_nada_guardado(pool: AsyncConnectionPool) -> None:
    repo = DebtRepository(pool)
    user, accounts, categories = await new_user(pool)
    debt = await repo.insert(user.id, new_debt())
    too_much = movement(accounts["USD"], categories["pago de deudas"], "25")
    with pytest.raises(DebtChanged):
        await repo.pay(user.id, debt, Decimal(25), too_much, "x")
    assert await usd_balance(pool, user.id) == 0  # el gasto se revirtió con el pago


async def test_liquidar_sin_movimiento_y_no_anular_con_pagos(pool: AsyncConnectionPool) -> None:
    repo = DebtRepository(pool)
    user, _, _ = await new_user(pool)
    debt = await repo.insert(user.id, new_debt())
    _, saved, after = await repo.pay(user.id, debt, Decimal(20), None, "se pagó la deuda")
    assert saved is None and after.status == "settled"
    assert await repo.list(user.id) == []
    [settled] = await repo.list(user.id, include_settled=True)
    assert settled.id == debt.id
    assert await repo.cancel(user.id, debt.id) == 0  # tiene un pago vigente


async def test_anular_y_aislamiento(pool: AsyncConnectionPool) -> None:
    repo = DebtRepository(pool)
    user, _, _ = await new_user(pool)
    other, _, _ = await new_user(pool)
    debt = await repo.insert(user.id, new_debt())
    assert await repo.cancel(other.id, debt.id) == 0
    assert await repo.get(other.id, debt.id) is None
    assert await repo.cancel(user.id, debt.id) == 1
    assert await repo.list(user.id) == []
    with pytest.raises(DebtChanged):
        await repo.pay(user.id, debt, Decimal(1), None, "x")


async def test_una_deuda_reciente_bloquea_la_correccion_por_mensaje(
    pool: AsyncConnectionPool,
) -> None:
    tx_repo, debts, corrections = (
        TransactionRepository(pool),
        DebtRepository(pool),
        CorrectionRepository(pool),
    )
    user, accounts, categories = await new_user(pool)
    await tx_repo.insert_many(user.id, [movement(accounts["USD"], categories["comida"], "3")])
    assert (await corrections.last_batch(user.id)).kind == "transactions"
    debt: Debt = await debts.insert(user.id, new_debt())
    assert (await corrections.last_batch(user.id)).kind == "debt"
    # El gasto de un pago comparte created_at con el pago: tampoco se corrige por mensaje.
    await debts.pay(
        user.id, debt, Decimal(5), movement(accounts["USD"], categories["pago de deudas"], "5"), "x"
    )
    assert (await corrections.last_batch(user.id)).kind == "debt"
