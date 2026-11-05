"""Vinculación con la web: el bot emite un código que la web canjea (ADR 0012)."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

import structlog

from gastos.domain.linking import LINK_TTL, new_code
from gastos.domain.user import User

# Una colisión entre códigos vigentes es casi imposible; se reintenta por si acaso.
MAX_ATTEMPTS = 3

log = structlog.get_logger()


class LinkStore(Protocol):
    """Lo que el servicio necesita de la persistencia (lo implementa db.LinkRepository)."""

    async def is_linked(self, user_id: UUID) -> bool: ...
    async def issue(self, user_id: UUID, code: str, expires_at: datetime) -> bool: ...


@dataclass(frozen=True)
class AlreadyLinked:
    pass


@dataclass(frozen=True)
class LinkCode:
    code: str
    expires_at: datetime


class LinkService:
    def __init__(
        self,
        store: LinkStore,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        generate: Callable[[], str] = new_code,
    ) -> None:
        self._store = store
        self._clock = clock
        self._generate = generate

    async def issue(self, user: User) -> AlreadyLinked | LinkCode:
        """Un código nuevo (anula los anteriores) o AlreadyLinked si ya tiene cuenta web."""
        if await self._store.is_linked(user.id):
            return AlreadyLinked()
        expires_at = self._clock() + LINK_TTL
        for _ in range(MAX_ATTEMPTS):
            code = self._generate()
            if await self._store.issue(user.id, code, expires_at):
                log.info("link_code_issued")
                return LinkCode(code, expires_at)
        raise RuntimeError("no se pudo generar un código de vinculación único")
