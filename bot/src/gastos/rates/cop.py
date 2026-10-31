"""Peso colombiano desde la API abierta de ExchangeRate-API (sin llave; se actualiza a diario).

Sus términos piden atribución con enlace donde se muestren las tasas (la pone /tasas) y
aceptan una consulta por hora; consultar más seguido da 429 durante 20 minutos.
"""

from datetime import datetime
from decimal import Decimal
from typing import Literal

import httpx
from pydantic import BaseModel

from gastos.domain.conversion import Rate, usd_per_unit_from
from gastos.rates.base import RateFetchError, fetch

URL = "https://open.er-api.com/v6/latest/USD"


class _Latest(BaseModel):
    result: Literal["success"]
    rates: dict[str, Decimal]  # unidades por USD


async def fetch_cop(http: httpx.AsyncClient, now: datetime) -> Rate:
    latest = await fetch(http, _Latest, "GET", URL)
    cop_per_usd = latest.rates.get("COP")
    if cop_per_usd is None or cop_per_usd <= 0:
        raise RateFetchError("er-api: la respuesta no trae COP")
    return Rate("COP", "fx", usd_per_unit_from(cop_per_usd), now)
