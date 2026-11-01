"""Consultas de la Fase 6 contra el Postgres de Supabase local (`.\\tasks.ps1 db-up`)."""

import os
import random
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from decimal import Decimal

import psycopg
import pytest
from psycopg_pool import AsyncConnectionPool

from gastos.db.pool import create_pool
from gastos.db.repositories.reports import ReportRepository
from gastos.db.repositories.transactions import TransactionRepository
from gastos.db.repositories.users import UserRepository
from gastos.domain.conversion import UsdSnapshot
from gastos.domain.currency import Currency
from gastos.domain.transaction import NewTransaction, TransactionKind
from gastos.domain.user import User

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://postgres:postgres@127.0.0.1:55322/postgres"
)
D = Decimal
OCT = (datetime(2026, 10, 1, tzinfo=UTC), datetime(2026, 11, 1, tzinfo=UTC))


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


async def seed(pool: AsyncConnectionPool) -> User:
    """Octubre: 2 gastos de comida en Bs, 1 de transporte en COP, 1 ingreso en USDT.
    Fuera de octubre: un gasto en septiembre. Y un gasto de octubre borrado."""
    user = await UserRepository(pool).create(random.randint(900000000000, 999999999999), None)
    repo = TransactionRepository(pool)
    accounts = {a.currency: a for a in await repo.accounts(user.id)}
    categories = {(c.name, c.kind): c for c in await repo.categories(user.id)}

    def tx(
        kind: TransactionKind,
        amount: int,
        currency: Currency,
        category: str,
        day: datetime,
        usd: str,
    ) -> NewTransaction:
        return NewTransaction(
            account=accounts[currency],
            kind=kind,
            amount=D(amount),
            category=categories[(category, kind)],
            description=category,
            snapshot=UsdSnapshot(D(1), "pivot", D(usd)),
            occurred_at=day,
            raw_text="seed",
            parse_confidence=1.0,
        )

    await repo.insert_many(
        user.id,
        [
            tx("expense", 500, "VES", "comida", datetime(2026, 10, 5, tzinfo=UTC), "0.5"),
            tx("expense", 700, "VES", "comida", datetime(2026, 10, 20, tzinfo=UTC), "0.7"),
            tx("expense", 20000, "COP", "transporte", datetime(2026, 10, 21, tzinfo=UTC), "5"),
            tx("income", 200, "USDT", "salario", datetime(2026, 10, 25, tzinfo=UTC), "199.8"),
            tx("expense", 999, "VES", "comida", datetime(2026, 9, 30, tzinfo=UTC), "1"),
        ],
    )
    [deleted] = await repo.insert_many(
        user.id,
        [tx("expense", 1, "USD", "ocio", datetime(2026, 10, 10, tzinfo=UTC), "1")],
    )
    await repo.undo_batch(user.id, deleted.id)
    return user


async def test_gasto_por_categoria_del_mes(pool: AsyncConnectionPool) -> None:
    user = await seed(pool)
    rows = await ReportRepository(pool).spending_by_category(user.id, *OCT, None)
    assert [(r.category, r.currency, r.amount, r.count) for r in rows] == [
        ("transporte", "COP", D(20000), 1),  # ordenado por su valor en USD
        ("comida", "VES", D(1200), 2),
    ]


async def test_totales_por_moneda_con_filtros(pool: AsyncConnectionPool) -> None:
    user = await seed(pool)
    repo = ReportRepository(pool)
    expenses = await repo.totals(user.id, "expense", *OCT, None, None)
    assert [(r.currency, r.amount, r.amount_usd) for r in expenses] == [
        ("COP", D(20000), D(5)),
        ("VES", D(1200), D("1.2")),
    ]
    food = await repo.totals(user.id, "expense", *OCT, "VES", "comida")
    assert [(r.amount, r.count) for r in food] == [(D(1200), 2)]
    income = await repo.totals(user.id, "income", *OCT, None, None)
    assert [(r.currency, r.amount) for r in income] == [("USDT", D(200))]


async def test_lista_ordenada_y_con_limite(pool: AsyncConnectionPool) -> None:
    user = await seed(pool)
    start = datetime(2000, 1, 1, tzinfo=UTC)
    rows = await ReportRepository(pool).list_transactions(
        user.id, start, OCT[1], None, None, None, 3
    )
    assert [(r.kind, r.amount) for r in rows] == [
        ("income", D(200)),
        ("expense", D(20000)),
        ("expense", D(700)),
    ]


async def test_saldos_y_aislamiento_entre_usuarios(pool: AsyncConnectionPool) -> None:
    user = await seed(pool)
    other = await seed(pool)
    repo = ReportRepository(pool)
    balances = {b.currency: b.balance for b in await repo.account_balances(user.id)}
    assert balances == {"COP": D(-20000), "USD": D(0), "USDT": D(200), "VES": D(-2199)}
    # Los datos del otro usuario no se cuelan en las consultas.
    rows = await repo.totals(other.id, "expense", *OCT, "VES", None)
    assert [r.amount for r in rows] == [D(1200)]
