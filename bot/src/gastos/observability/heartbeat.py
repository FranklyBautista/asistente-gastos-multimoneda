"""Latido externo: avisa a un servicio de monitoreo (healthchecks.io) que el bot sigue vivo.

El job de tasas lo llama en cada refresco: si el aviso deja de llegar (el bot se cayó o el
scheduler se trabó) o llega como fallo (ninguna fuente respondió), el servicio manda una
alerta por correo. Sin `HEALTHCHECK_URL` no se usa.
"""

from collections.abc import Awaitable, Callable

import httpx


def healthcheck_ping(http: httpx.AsyncClient, url: str) -> Callable[[bool], Awaitable[None]]:
    """`url` es la de ping del chequeo; `<url>/fail` marca el chequeo como fallido."""
    base = url.rstrip("/")

    async def ping(ok: bool) -> None:
        response = await http.get(base if ok else f"{base}/fail", timeout=10)
        response.raise_for_status()

    return ping
