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
