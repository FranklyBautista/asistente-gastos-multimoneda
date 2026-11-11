"""Casos de uso de tasas: refrescarlas desde las fuentes y leer la vigente desde la BD.

El bot nunca consulta una API al responder un mensaje: lee la última tasa guardada. Si una
fuente se cae, se sigue usando su última tasa y se marca como vieja pasado `max_age`.
"""

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Final, Protocol

import structlog

from gastos.domain.conversion import Rate, is_stale
from gastos.domain.currency import QuotedCurrency, RateSource, VesRateSource, rate_source_for
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
    async def at(
        self, currency: QuotedCurrency, source: RateSource, moment: datetime
    ) -> Rate | None: ...


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
    # La fuente que se pidió, si no tenía tasa fresca y se usó otra (solo el bolívar).
    replaced: RateSource | None = None


# Si la fuente del Bs del usuario no tiene tasa fresca, la primera fresca de esta lista.
VES_FALLBACK: Final[tuple[VesRateSource, ...]] = ("parallel", "bcv", "p2p")
# Una tasa que se mueve más que esto frente a la última guardada es sospechosa (un decimal
# corrido en la fuente). Se descarta, salvo que se repita en refrescos seguidos.
MAX_JUMP: Final = Decimal("0.25")
JUMP_CONFIRMATIONS: Final = 3

# Aviso externo de que el refresco corrió (healthchecks.io u otro): True si llegó alguna tasa.
Heartbeat = Callable[[bool], Awaitable[None]]


async def _as_list(rate: Awaitable[Rate]) -> list[Rate]:
    return [await rate]


class RateService:
    def __init__(
        self,
        store: RateStore,
        sources: RateSources,
        max_age: timedelta,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        heartbeat: Heartbeat | None = None,
    ) -> None:
        self._store = store
        self._sources = sources
        self._max_age = max_age
        self._clock = clock
        self._heartbeat = heartbeat
        # Saltos rechazados seguidos por moneda y fuente.
        self._jumps: dict[tuple[QuotedCurrency, RateSource], int] = {}

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
        fetched = await self._plausible(fetched)
        if fetched:
            await self._store.save(fetched)
        log.info("rates_refreshed", saved=len(fetched), expected=len(BOARD))
        if self._heartbeat is not None:
            try:
                await self._heartbeat(bool(fetched))
            except Exception as exc:  # el aviso externo nunca debe frenar el refresco
                log.warning("heartbeat_failed", error=type(exc).__name__)
        return fetched

    async def _plausible(self, fetched: list[Rate]) -> list[Rate]:
        """Descarta los saltos de más de MAX_JUMP frente a la última tasa guardada.

        Un salto real (una devaluación brusca) se acepta cuando se repite JUMP_CONFIRMATIONS
        refrescos seguidos; un dato roto de la fuente casi nunca dura tanto.
        """
        accepted: list[Rate] = []
        for rate in fetched:
            key = (rate.currency, rate.source)
            last = await self._store.latest(*key)
            change = None if last is None else rate.usd_per_unit / last.usd_per_unit - 1
            if change is None or abs(change) <= MAX_JUMP:
                self._jumps.pop(key, None)
                accepted.append(rate)
                continue
            seen = self._jumps.get(key, 0) + 1
            fields = {"currency": rate.currency, "source": rate.source, "change": f"{change:.2%}"}
            if seen >= JUMP_CONFIRMATIONS:
                log.warning("rate_jump_accepted", times=seen, **fields)
                self._jumps.pop(key, None)
                accepted.append(rate)
            else:
                log.warning("rate_jump_rejected", times=seen, **fields)
                self._jumps[key] = seen
        return accepted

    async def current(self, currency: QuotedCurrency, source: RateSource) -> CurrentRate:
        """La última tasa guardada; lanza RateUnavailable si nunca se pudo obtener."""
        rate = await self._store.latest(currency, source)
        if rate is None:
            raise RateUnavailable(currency, source)
        return CurrentRate(rate, is_stale(rate, self._clock(), self._max_age))

    async def for_user(self, user: User, currency: QuotedCurrency) -> CurrentRate:
        """La tasa que corresponde al usuario: la del bolívar sale de su preferencia.

        Si su fuente del Bs no tiene tasa fresca (nunca se pudo obtener, o lleva más de
        max_age sin responder), se usa la primera fuente fresca de VES_FALLBACK y se marca
        en `replaced` para avisarle. Si ninguna está fresca, la suya aunque esté vieja.
        """
        preferred = rate_source_for(currency, user.ves_rate_source)
        if currency != "VES":
            return await self.current(currency, preferred)
        now = self._clock()
        found: list[Rate] = []
        candidates: list[RateSource] = [preferred, *(s for s in VES_FALLBACK if s != preferred)]
        for source in candidates:
            rate = await self._store.latest("VES", source)
            if rate is None:
                continue
            if not is_stale(rate, now, self._max_age):
                replaced = None if source == preferred else preferred
                return CurrentRate(rate, stale=False, replaced=replaced)
            found.append(rate)
        if not found:
            raise RateUnavailable(currency, preferred)
        best = found[0]  # la preferida si existe; si no, la primera vieja de la lista
        replaced = None if best.source == preferred else preferred
        return CurrentRate(best, stale=True, replaced=replaced)

    async def for_user_at(
        self, user: User, currency: QuotedCurrency, moment: datetime
    ) -> Rate | None:
        """La tasa del usuario vigente en `moment` (la primera posterior si no hay anterior)."""
        source = rate_source_for(currency, user.ves_rate_source)
        return await self._store.at(currency, source, moment)

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
