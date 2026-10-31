"""Casos de uso de tasas: refrescarlas desde las fuentes y leer la vigente desde la BD.

El bot nunca consulta una API al responder un mensaje: lee la última tasa guardada. Si una
fuente se cae, se sigue usando su última tasa y se marca como vieja pasado `max_age`.
"""

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Final, Protocol

import structlog

from gastos.domain.conversion import Rate, is_stale
from gastos.domain.currency import QuotedCurrency, RateSource, rate_source_for
from gastos.domain.errors import RateUnavailable
from gastos.domain.user import User

log = structlog.get_logger()

# Todas las tasas que se guardan, en el orden en que se muestran.
BOARD: Final[tuple[tuple[QuotedCurrency, RateSource], ...]] = (
    ("VES", "bcv"),
    ("VES", "parallel"),
    ("VES", "p2p"),
    ("COP", "fx"),
    ("USDT", "coingecko"),
)


class RateStore(Protocol):
    """Lo que el servicio necesita de la persistencia (lo implementa db.RateRepository)."""

    async def save(self, rates: Sequence[Rate]) -> None: ...
    async def latest(self, currency: QuotedCurrency, source: RateSource) -> Rate | None: ...


class RateSources(Protocol):
    """Las APIs externas (lo implementa rates.HttpRateSources)."""

    async def ves_dolarapi(self) -> list[Rate]: ...
    async def ves_p2p(self, usdt_rate: Rate) -> Rate: ...
    async def cop(self) -> Rate: ...
    async def usdt(self) -> Rate: ...


@dataclass(frozen=True, slots=True)
class CurrentRate:
    rate: Rate
    stale: bool  # su fuente lleva más de max_age sin responder; se usa la última guardada


async def _as_list(rate: Awaitable[Rate]) -> list[Rate]:
    return [await rate]


class RateService:
    def __init__(
        self,
        store: RateStore,
        sources: RateSources,
        max_age: timedelta,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._store = store
        self._sources = sources
        self._max_age = max_age
        self._clock = clock

    async def refresh(self) -> list[Rate]:
        """Consulta cada fuente por separado y guarda lo que llegue."""
        sources = self._sources
        ves, cop, usdt = await asyncio.gather(
            self._attempt("dolarapi", sources.ves_dolarapi),
            self._attempt("er_api", lambda: _as_list(sources.cop())),
            self._attempt("coingecko", lambda: _as_list(sources.usdt())),
        )
        fetched = [*ves, *cop, *usdt]
        # El P2P cotiza en USDT: se cruza con el USDT recién leído o, si falló, con el guardado.
        usdt_rate = usdt[0] if usdt else await self._store.latest("USDT", "coingecko")
        if usdt_rate is None:
            log.warning("rate_fetch_skipped", source="binance_p2p", reason="no_usdt_rate")
        else:
            fetched += await self._attempt(
                "binance_p2p", lambda: _as_list(sources.ves_p2p(usdt_rate))
            )
        if fetched:
            await self._store.save(fetched)
        log.info("rates_refreshed", saved=len(fetched), expected=len(BOARD))
        return fetched

    async def current(self, currency: QuotedCurrency, source: RateSource) -> CurrentRate:
        """La última tasa guardada; lanza RateUnavailable si nunca se pudo obtener."""
        rate = await self._store.latest(currency, source)
        if rate is None:
            raise RateUnavailable(currency, source)
        return CurrentRate(rate, is_stale(rate, self._clock(), self._max_age))

    async def for_user(self, user: User, currency: QuotedCurrency) -> CurrentRate:
        """La tasa que corresponde al usuario: la del bolívar sale de su preferencia."""
        return await self.current(currency, rate_source_for(currency, user.ves_rate_source))

    async def board(self) -> list[tuple[QuotedCurrency, RateSource, CurrentRate | None]]:
        """Todas las tasas, con None en las que todavía no se han podido obtener."""
        board: list[tuple[QuotedCurrency, RateSource, CurrentRate | None]] = []
        for currency, source in BOARD:
            try:
                board.append((currency, source, await self.current(currency, source)))
            except RateUnavailable:
                board.append((currency, source, None))
        return board

    @staticmethod
    async def _attempt(source: str, fetch: Callable[[], Awaitable[list[Rate]]]) -> list[Rate]:
        try:
            return await fetch()
        except Exception as exc:  # una fuente caída nunca debe frenar a las demás
            log.warning("rate_fetch_failed", source=source, error=type(exc).__name__)
            return []
