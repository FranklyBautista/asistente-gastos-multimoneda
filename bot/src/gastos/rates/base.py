"""Piezas comunes de los clientes de tasas."""

from decimal import Decimal
from typing import Any

import httpx
from pydantic import TypeAdapter, ValidationError

USER_AGENT = (
    "asistente-gastos-multimoneda "
    "(+https://github.com/FranklyBautista/asistente-gastos-multimoneda)"
)


class RateFetchError(Exception):
    """Una fuente no respondió o respondió algo que no se pudo interpretar."""


def create_http_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=10, headers={"User-Agent": USER_AGENT})


async def fetch[T](
    http: httpx.AsyncClient, schema: type[T], method: str, url: str, **kwargs: Any
) -> T:
    """Pide un JSON y lo valida con `schema`; cualquier fallo sale como RateFetchError.

    Los números del JSON se leen como Decimal para no pasar nunca por float.
    """
    try:
        response = await http.request(method, url, **kwargs)
        response.raise_for_status()
        data = response.json(parse_float=Decimal)
    except (httpx.HTTPError, ValueError) as exc:  # ValueError: el cuerpo no es JSON
        raise RateFetchError(f"{url}: {type(exc).__name__}") from exc
    try:
        return TypeAdapter(schema).validate_python(data)
    except ValidationError as exc:
        raise RateFetchError(f"{url}: formato inesperado") from exc
