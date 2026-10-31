"""Comando /tasas: las tasas vigentes, con aviso si alguna fuente lleva tiempo sin responder."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Final

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import LinkPreviewOptions, Message

from gastos.domain.conversion import units_per_usd
from gastos.domain.currency import QuotedCurrency, RateSource, VesRateSource
from gastos.domain.user import User
from gastos.services.rates import CurrentRate, RateService

router = Router(name="rates")

LABELS: Final[dict[RateSource, str]] = {
    "bcv": "Bs · BCV",
    "parallel": "Bs · paralelo",
    "p2p": "Bs · P2P",
    "fx": "COP",
    "coingecko": "USDT",
}
STALE_NOTE = "⚠️ Esa fuente no responde; mientras tanto uso la última tasa guardada."
# Los términos de ExchangeRate-API piden atribución con enlace donde se muestren sus tasas.
SOURCES_NOTE = (
    "Fuentes: DolarApi (BCV y paralelo), Binance P2P, CoinGecko y, para COP, "
    "Rates By Exchange Rate API (https://www.exchangerate-api.com)."
)

Board = list[tuple[QuotedCurrency, RateSource, CurrentRate | None]]


def format_number(value: Decimal, decimals: int) -> str:
    """1234.5 → "1.234,50", como se escriben los montos en Venezuela y Colombia."""
    return f"{value:,.{decimals}f}".replace(",", "_").replace(".", ",").replace("_", ".")


def format_age(delta: timedelta) -> str:
    hours = int(delta.total_seconds() // 3600)
    if hours >= 48:
        return f"{hours // 24} días"
    if hours >= 1:
        return f"{hours} h"
    return f"{max(1, int(delta.total_seconds() // 60))} min"


def _line(
    currency: QuotedCurrency,
    source: RateSource,
    current: CurrentRate | None,
    ves_source: VesRateSource,
    now: datetime,
) -> str:
    label = LABELS[source]
    if current is None:
        return f"{label}: sin datos todavía"
    rate = current.rate
    if currency == "USDT":
        line = f"{label}: {format_number(rate.usd_per_unit, 4)} USD"
    else:
        line = f"{label}: {format_number(units_per_usd(rate), 2)} por USD"
    if source == ves_source:
        line += " ← la tuya"
    if current.stale:
        line += f" ⚠️ sin actualizar hace {format_age(now - rate.fetched_at)}"
    return line


def rates_text(board: Board, ves_source: VesRateSource, now: datetime) -> str:
    lines = ["Tasas de cambio:", ""]
    lines += [
        _line(currency, source, current, ves_source, now) for currency, source, current in board
    ]
    if any(current and current.stale for _, _, current in board):
        lines += ["", STALE_NOTE]
    lines += ["", SOURCES_NOTE]
    return "\n".join(lines)


@router.message(Command("tasas"))
async def show_rates(message: Message, user: User, rates: RateService) -> None:
    text = rates_text(await rates.board(), user.ves_rate_source, datetime.now(UTC))
    await message.answer(text, link_preview_options=LinkPreviewOptions(is_disabled=True))
