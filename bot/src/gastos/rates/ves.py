"""Bolívar: BCV y paralelo desde DolarApi; P2P desde los anuncios de Binance P2P.

Ninguna de las dos fuentes llama VED al bolívar; si alguna lo hiciera, el mapeo a VES va aquí.
"""

import asyncio
from datetime import datetime
from decimal import Decimal
from statistics import median
from typing import Final

import httpx
from pydantic import BaseModel, Field

from gastos.domain.conversion import Rate, usd_per_unit_from
from gastos.domain.currency import VesRateSource
from gastos.rates.base import RateFetchError, fetch

DOLARAPI_URL = "https://ve.dolarapi.com/v1/dolares"
# Endpoint público pero no documentado de la web de Binance P2P: puede cambiar sin aviso.
BINANCE_P2P_URL = "https://p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search"
P2P_ADS = 10  # anuncios por lado que entran en la mediana
P2P_MIN_ADS = 3

_DOLARAPI_SOURCES: Final[dict[str, VesRateSource]] = {"oficial": "bcv", "paralelo": "parallel"}


class _DolarApiQuote(BaseModel):
    fuente: str
    promedio: Decimal | None = Field(default=None, gt=0)  # Bs por USD


class _P2PAdv(BaseModel):
    price: Decimal = Field(gt=0)  # Bs por USDT


class _P2PAd(BaseModel):
    adv: _P2PAdv


class _P2PSearch(BaseModel):
    data: list[_P2PAd]


async def fetch_dolarapi(http: httpx.AsyncClient, now: datetime) -> list[Rate]:
    """Tasas BCV y paralelo (DolarApi publica el promedio en Bs por USD)."""
    quotes = await fetch(http, list[_DolarApiQuote], "GET", DOLARAPI_URL)
    rates = [
        Rate("VES", _DOLARAPI_SOURCES[q.fuente], usd_per_unit_from(q.promedio), now)
        for q in quotes
        if q.fuente in _DOLARAPI_SOURCES and q.promedio is not None
    ]
    if not rates:
        raise RateFetchError("dolarapi: la respuesta no trae BCV ni paralelo")
    return rates


async def _p2p_median(http: httpx.AsyncClient, trade_type: str) -> Decimal:
    body = {
        "asset": "USDT",
        "fiat": "VES",
        "tradeType": trade_type,
        "page": 1,
        "rows": P2P_ADS,
        "payTypes": [],
        "publisherType": None,
    }
    search = await fetch(http, _P2PSearch, "POST", BINANCE_P2P_URL, json=body)
    prices = [ad.adv.price for ad in search.data[:P2P_ADS]]
    if len(prices) < P2P_MIN_ADS:
        raise RateFetchError(f"binance p2p: solo {len(prices)} anuncios de {trade_type}")
    return median(prices)  # la mediana ignora anuncios con precios atípicos


async def fetch_p2p(http: httpx.AsyncClient, usdt: Rate, now: datetime) -> Rate:
    """Tasa P2P: punto medio entre compra y venta de USDT, cruzado con el precio del USDT.

    En P2P se cotiza Bs por USDT, no por USD (ADR 0002: USDT no es USD).
    """
    if usdt.currency != "USDT":
        raise ValueError(f"el P2P se cruza con la tasa de USDT, no de {usdt.currency}")
    buy, sell = await asyncio.gather(_p2p_median(http, "BUY"), _p2p_median(http, "SELL"))
    ves_per_usdt = (buy + sell) / 2
    return Rate(
        "VES", "p2p", usd_per_unit_from(ves_per_usdt, quote_usd_per_unit=usdt.usd_per_unit), now
    )
