"""Pool de conexiones a Postgres (credenciales de servicio: se salta la RLS)."""

from psycopg_pool import AsyncConnectionPool


def create_pool(database_url: str) -> AsyncConnectionPool:
    """Crea el pool sin abrirlo; se abre con `await pool.open()` al arrancar.

    `prepare_threshold=None` desactiva los prepared statements para que funcione
    también con el pooler de Supabase en modo transacción.
    """
    return AsyncConnectionPool(
        database_url,
        open=False,
        min_size=1,
        max_size=5,
        kwargs={"prepare_threshold": None},
    )


async def ping(pool: AsyncConnectionPool, wait_seconds: float = 5) -> bool:
    """`True` si la base de datos responde; lo usa el healthcheck del despliegue."""
    try:
        async with pool.connection(timeout=wait_seconds) as conn:
            await conn.execute("select 1")
    except Exception:
        return False
    return True
