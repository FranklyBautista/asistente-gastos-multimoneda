"""Interfaz común de los proveedores de LLM: prompt y esquema Pydantic → objeto validado."""

from typing import Protocol

from pydantic import BaseModel


class LLMClient(Protocol):
    async def structured[T: BaseModel](self, *, system: str, prompt: str, schema: type[T]) -> T:
        """Devuelve la salida ya validada contra `schema`.

        Lanza `domain.errors.LLMUnavailable` si el proveedor no responde o, tras un
        reintento, su salida sigue sin validar.
        """
        ...
