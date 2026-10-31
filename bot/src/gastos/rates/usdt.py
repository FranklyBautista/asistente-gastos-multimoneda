"""USDT desde CoinGecko (API pública sin llave; límite de unas pocas consultas por minuto)."""

from datetime import datetime
from decimal import ROUND_HALF_EVEN, Decimal

import httpx
from pydantic import BaseModel, Field

from gastos.domain.conversion import RATE_SCALE, Rate
from gastos.rates.base import fetch

URL = "https://api.coingecko.com/api/v3/simple/price"


class _Price(BaseModel):
    usd: Decimal = Field(gt=0)  # USD por 1 USDT: ya viene como usd_per_unit


class _SimplePrice(BaseModel):
    tether: _Price


async def fetch_usdt(http: httpx.AsyncClient, now: datetime) -> Rate:
    price = await fetch(
        http, _SimplePrice, "GET", URL, params={"ids": "tether", "vs_currencies": "usd"}
    )
    usd_per_unit = price.tether.usd.quantize(RATE_SCALE, rounding=ROUND_HALF_EVEN)
    return Rate("USDT", "coingecko", usd_per_unit, now)
