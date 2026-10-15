"""Casos de uso de usuarios: identificar a quien escribe y guardar su onboarding."""

from typing import Protocol
from uuid import UUID

from gastos.domain.currency import Currency, VesRateSource, parse_currency, parse_ves_rate_source
from gastos.domain.user import User, parse_timezone


class UserStore(Protocol):
    """Lo que el servicio necesita de la persistencia (lo implementa db.UserRepository)."""

    async def get_by_telegram_id(self, telegram_id: int) -> User | None: ...
    async def create(self, telegram_id: int, display_name: str | None) -> User: ...
    async def set_default_currency(self, user_id: UUID, currency: Currency) -> User: ...
    async def set_ves_rate_source(self, user_id: UUID, source: VesRateSource) -> User: ...
    async def complete_onboarding(self, user_id: UUID, timezone: str) -> User: ...


class UserService:
    def __init__(self, store: UserStore) -> None:
        self._store = store

    async def identify(self, telegram_id: int, display_name: str | None) -> User:
        """Devuelve el usuario de ese telegram_id y lo registra si es la primera vez."""
        user = await self._store.get_by_telegram_id(telegram_id)
        if user is not None:
            return user
        return await self._store.create(telegram_id, display_name)

    async def choose_currency(self, user: User, value: str) -> User:
        return await self._store.set_default_currency(user.id, parse_currency(value))

    async def choose_ves_rate_source(self, user: User, value: str) -> User:
        return await self._store.set_ves_rate_source(user.id, parse_ves_rate_source(value))

    async def finish_onboarding(self, user: User, timezone: str) -> User:
        return await self._store.complete_onboarding(user.id, parse_timezone(timezone))
