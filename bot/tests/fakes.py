"""Dobles de prueba compartidos (sin red ni base de datos)."""

from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

from gastos.domain.currency import Currency, VesRateSource
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
