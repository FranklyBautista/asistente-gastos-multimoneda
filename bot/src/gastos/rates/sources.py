"""Las fuentes reales, reunidas en el objeto que usa services.rates.RateService."""

from collections.abc import Callable
from datetime import UTC, datetime

import httpx

from gastos.domain.conversion import Rate
from gastos.rates import cop, usdt, ves

Clock = Callable[[], datetime]


def utc_now() -> datetime:
    return datetime.now(UTC)


class HttpRateSources:
    """Implementa services.rates.RateSources; cada tasa lleva la hora en que se consultó."""

    def __init__(self, http: httpx.AsyncClient, clock: Clock = utc_now) -> None:
        self._http = http
        self._clock = clock

    async def ves_dolarapi(self) -> list[Rate]:
        return await ves.fetch_dolarapi(self._http, self._clock())

    async def ves_p2p(self, usdt_rate: Rate) -> Rate:
        return await ves.fetch_p2p(self._http, usdt_rate, self._clock())

    async def cop(self) -> Rate:
        return await cop.fetch_cop(self._http, self._clock())

    async def usdt(self) -> Rate:
        return await usdt.fetch_usdt(self._http, self._clock())
