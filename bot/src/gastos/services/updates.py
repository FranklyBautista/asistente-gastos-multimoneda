"""Idempotencia de updates de Telegram (ADR 0011).

Telegram puede entregar dos veces el mismo update. Cada update se reserva por su `update_id`
antes de procesarlo; si ya estaba reservado, se descarta. Se prefiere perder un update a
anotarlo dos veces: si el bot se cae a mitad de uno, el usuario no recibe confirmación y
puede volver a escribirlo, mientras que un gasto duplicado pasa inadvertido.
"""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Protocol

import structlog

# Telegram guarda los updates sin entregar 24 h; con 2 días hay margen de sobra.
RETENTION = timedelta(days=2)

log = structlog.get_logger()


class UpdateStore(Protocol):
    """Lo que el servicio necesita de la persistencia (lo implementa db.UpdateRepository)."""

    async def claim(self, bot_id: int, update_id: int) -> bool: ...
    async def purge_before(self, cutoff: datetime) -> int: ...


class UpdateLedger:
    def __init__(
        self, store: UpdateStore, *, clock: Callable[[], datetime] = lambda: datetime.now(UTC)
    ) -> None:
        self._store = store
        self._clock = clock

    async def first_time(self, bot_id: int, update_id: int) -> bool:
        """True la primera vez que llega ese update; False si es una repetición."""
        return await self._store.claim(bot_id, update_id)

    async def purge(self) -> None:
        """Borra los registros viejos; lo corre el programador una vez al día."""
        deleted = await self._store.purge_before(self._clock() - RETENTION)
        log.info("processed_updates_purged", deleted=deleted)
