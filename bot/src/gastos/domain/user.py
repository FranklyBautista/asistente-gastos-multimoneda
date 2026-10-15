"""Usuario del bot y sus preferencias."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from gastos.domain.currency import Currency, VesRateSource
from gastos.domain.errors import InvalidPreference


@dataclass(frozen=True, slots=True)
class User:
    id: UUID
    telegram_id: int
    display_name: str | None
    timezone: str
    default_currency: Currency
    ves_rate_source: VesRateSource
    onboarded_at: datetime | None

    @property
    def is_onboarded(self) -> bool:
        return self.onboarded_at is not None


def parse_timezone(value: str) -> str:
    """Valida un nombre IANA (por ejemplo America/Caracas); lanza InvalidPreference si no existe."""
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise InvalidPreference("timezone", value) from exc
    return value
