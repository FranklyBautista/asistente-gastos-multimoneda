"""Clientes de tasas contra respuestas simuladas (ninguna prueba sale a internet)."""

import json
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import httpx
import pytest

from gastos.domain.conversion import Rate, usd_per_unit_from
from gastos.rates import cop, usdt, ves
from gastos.rates.base import RateFetchError
from gastos.rates.sources import HttpRateSources

NOW = datetime(2026, 10, 27, 12, tzinfo=UTC)
USDT_RATE = Rate("USDT", "coingecko", Decimal("0.999"), NOW)

Handler = Callable[[httpx.Request], httpx.Response]


def mock_http(handler: Handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def json_response(payload: Any) -> Handler:
    return lambda request: httpx.Response(200, json=payload)


def dolarapi_quote(fuente: str, promedio: Any) -> dict[str, Any]:
    return {"moneda": "USD", "fuente": fuente, "promedio": promedio, "compra": None}


def p2p_page(prices: list[str]) -> dict[str, Any]:
    return {"code": "000000", "success": True, "data": [{"adv": {"price": p}} for p in prices]}


async def test_dolarapi_trae_bcv_y_paralelo_sin_pasar_por_float() -> None:
    payload = [dolarapi_quote("oficial", 800), dolarapi_quote("paralelo", 1001.324308)]
    async with mock_http(json_response(payload)) as http:
        rates = await ves.fetch_dolarapi(http, NOW)
    assert rates == [
        Rate("VES", "bcv", Decimal("0.00125"), NOW),
        Rate("VES", "parallel", usd_per_unit_from(Decimal("1001.324308")), NOW),
    ]


async def test_dolarapi_sin_tasas_utiles_es_un_fallo() -> None:
    payload = [dolarapi_quote("oficial", None), dolarapi_quote("bitcoin", 5)]
    async with mock_http(json_response(payload)) as http:
        with pytest.raises(RateFetchError):
            await ves.fetch_dolarapi(http, NOW)


async def test_p2p_usa_la_mediana_de_cada_lado_y_cruza_con_usdt() -> None:
    pages = {
        "BUY": ["980", "1004", "1005", "1006", "1007"],  # 980: anuncio atípico
        "SELL": ["1030", "1031", "1006", "1007", "1008"],
    }
    seen: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        seen.append(body)
        return httpx.Response(200, json=p2p_page(pages[body["tradeType"]]))

    async with mock_http(handler) as http:
        rate = await ves.fetch_p2p(http, USDT_RATE, NOW)
    # Mediana de compra 1005 y de venta 1008: 1006,5 Bs por USDT.
    expected = usd_per_unit_from(Decimal("1006.5"), quote_usd_per_unit=Decimal("0.999"))
    assert rate == Rate("VES", "p2p", expected, NOW)
    assert {(b["asset"], b["fiat"], b["tradeType"]) for b in seen} == {
        ("USDT", "VES", "BUY"),
        ("USDT", "VES", "SELL"),
    }


async def test_p2p_con_pocos_anuncios_es_un_fallo() -> None:
    async with mock_http(json_response(p2p_page(["1000", "1001"]))) as http:
        with pytest.raises(RateFetchError):
            await ves.fetch_p2p(http, USDT_RATE, NOW)


async def test_p2p_exige_la_tasa_del_usdt() -> None:
    async with mock_http(json_response(p2p_page(["1000"] * 5))) as http:
        with pytest.raises(ValueError):
            await ves.fetch_p2p(http, Rate("VES", "bcv", Decimal("0.001"), NOW), NOW)


async def test_cop_desde_er_api() -> None:
    payload = {"result": "success", "base_code": "USD", "rates": {"USD": 1, "COP": 4000}}
    async with mock_http(json_response(payload)) as http:
        assert await cop.fetch_cop(http, NOW) == Rate("COP", "fx", Decimal("0.00025"), NOW)


@pytest.mark.parametrize(
    "payload",
    [
        {"result": "success", "rates": {"USD": 1}},
        {"result": "error", "error-type": "unsupported-code"},
    ],
)
async def test_cop_sin_dato_es_un_fallo(payload: dict[str, Any]) -> None:
    async with mock_http(json_response(payload)) as http:
        with pytest.raises(RateFetchError):
            await cop.fetch_cop(http, NOW)


async def test_usdt_desde_coingecko() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"tether": {"usd": 0.998781}})

    async with mock_http(handler) as http:
        rate = await usdt.fetch_usdt(http, NOW)
    assert rate == Rate("USDT", "coingecko", Decimal("0.998781"), NOW)
    assert seen[0].url.params["ids"] == "tether"


def _server_error(request: httpx.Request) -> httpx.Response:
    return httpx.Response(500, text="error")


def _not_json(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, text="<html>mantenimiento</html>")


def _network_down(request: httpx.Request) -> httpx.Response:
    raise httpx.ConnectError("sin conexión", request=request)


Fetcher = Callable[[httpx.AsyncClient], Awaitable[object]]
FETCHERS: dict[str, Fetcher] = {
    "dolarapi": lambda http: ves.fetch_dolarapi(http, NOW),
    "p2p": lambda http: ves.fetch_p2p(http, USDT_RATE, NOW),
    "cop": lambda http: cop.fetch_cop(http, NOW),
    "usdt": lambda http: usdt.fetch_usdt(http, NOW),
}


@pytest.mark.parametrize("fetcher", FETCHERS.values(), ids=FETCHERS.keys())
@pytest.mark.parametrize("handler", [_server_error, _not_json, _network_down])
async def test_cualquier_falla_de_la_fuente_sale_como_rate_fetch_error(
    fetcher: Fetcher, handler: Handler
) -> None:
    async with mock_http(handler) as http:
        with pytest.raises(RateFetchError):
            await fetcher(http)


async def test_las_fuentes_marcan_la_hora_de_consulta() -> None:
    async with mock_http(json_response({"tether": {"usd": 1}})) as http:
        rate = await HttpRateSources(http, clock=lambda: NOW).usdt()
    assert rate.fetched_at == NOW
