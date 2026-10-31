"""Dobles de prueba compartidos (sin red ni base de datos)."""

from collections.abc import Sequence
from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

from gastos.domain.conversion import Rate
from gastos.domain.currency import Currency, QuotedCurrency, RateSource, VesRateSource
from gastos.domain.user import User


def make_user(telegram_id: int = 111, *, onboarded: bool = False) -> User:
    return User(
        id=uuid4(),
        telegram_id=telegram_id,
        display_name="Ana",
        timezone="America/Caracas",
        default_currency="USD",
        ves_rate_source="parallel",
        onboarded_at=datetime(2026, 10, 15, tzinfo=UTC) if onboarded else None,
    )


class FakeUserStore:
    """Implementa services.users.UserStore en memoria."""

    def __init__(self) -> None:
        self.by_id: dict[UUID, User] = {}
        self.created = 0

    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        return next((u for u in self.by_id.values() if u.telegram_id == telegram_id), None)

    async def create(self, telegram_id: int, display_name: str | None) -> User:
        self.created += 1
        user = replace(make_user(telegram_id), display_name=display_name)
        self.by_id[user.id] = user
        return user

    async def set_default_currency(self, user_id: UUID, currency: Currency) -> User:
        return self._save(replace(self.by_id[user_id], default_currency=currency))

    async def set_ves_rate_source(self, user_id: UUID, source: VesRateSource) -> User:
        return self._save(replace(self.by_id[user_id], ves_rate_source=source))

    async def complete_onboarding(self, user_id: UUID, timezone: str) -> User:
        current = self.by_id[user_id]
        onboarded_at = current.onboarded_at or datetime.now(UTC)
        return self._save(replace(current, timezone=timezone, onboarded_at=onboarded_at))

    def _save(self, user: User) -> User:
        self.by_id[user.id] = user
        return user


class FakeRateStore:
    """Implementa services.rates.RateStore en memoria."""

    def __init__(self, *rates: Rate) -> None:
        self.rows: list[Rate] = list(rates)

    async def save(self, rates: Sequence[Rate]) -> None:
        self.rows.extend(rates)

    async def latest(self, currency: QuotedCurrency, source: RateSource) -> Rate | None:
        matching = [r for r in self.rows if (r.currency, r.source) == (currency, source)]
        return max(matching, key=lambda r: r.fetched_at, default=None)


class FakeRateSources:
    """Implementa services.rates.RateSources; una fuente con una excepción simula una caída."""

    def __init__(
        self,
        *,
        dolarapi: list[Rate] | Exception,
        p2p: Rate | Exception,
        cop: Rate | Exception,
        usdt: Rate | Exception,
    ) -> None:
        self._dolarapi = dolarapi
        self._p2p = p2p
        self._cop = cop
        self._usdt = usdt
        self.p2p_crossed_with: Rate | None = None

    async def ves_dolarapi(self) -> list[Rate]:
        return _or_raise(self._dolarapi)

    async def ves_p2p(self, usdt_rate: Rate) -> Rate:
        self.p2p_crossed_with = usdt_rate
        return _or_raise(self._p2p)

    async def cop(self) -> Rate:
        return _or_raise(self._cop)

    async def usdt(self) -> Rate:
        return _or_raise(self._usdt)


def _or_raise[T](result: T | Exception) -> T:
    if isinstance(result, Exception):
        raise result
    return result
