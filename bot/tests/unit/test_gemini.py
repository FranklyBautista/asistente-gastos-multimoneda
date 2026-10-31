"""Adaptador de Gemini con un cliente falso: respaldo entre modelos, reintento y tiempo límite."""

import asyncio
from types import SimpleNamespace
from typing import Any, cast

import pytest
from google import genai
from google.genai import errors
from pydantic import BaseModel

from gastos.domain.errors import LLMUnavailable
from gastos.extraction.schema import Extraction
from gastos.llm.gemini import GeminiClient


class Out(BaseModel):
    value: int


def busy() -> errors.ServerError:
    return errors.ServerError(503, {"error": {"code": 503, "status": "UNAVAILABLE"}})


class FakeModels:
    """Responde por modelo, en orden: str = texto de la respuesta; Exception = se lanza."""

    def __init__(self, script: dict[str, list[str | Exception]]) -> None:
        self.script = script
        self.calls: list[str] = []
        self.configs: list[Any] = []

    async def generate_content(self, *, model: str, contents: str, config: Any) -> Any:
        self.calls.append(model)
        self.configs.append(config)
        step = self.script[model].pop(0)
        if isinstance(step, Exception):
            raise step
        if step == "SLOW":
            await asyncio.sleep(1)
        return SimpleNamespace(text=step)


def client_with(script: dict[str, list[str | Exception]], **kwargs: Any) -> tuple[Any, FakeModels]:
    models = FakeModels(script)
    fake = cast(genai.Client, SimpleNamespace(aio=SimpleNamespace(models=models)))
    return GeminiClient("llave", list(script), client=fake, **kwargs), models


async def test_devuelve_la_salida_validada() -> None:
    llm, _ = client_with({"principal": ['{"value": 3}']})
    assert await llm.structured(system="s", prompt="p", schema=Out) == Out(value=3)


async def test_salida_invalida_se_reintenta_una_vez() -> None:
    llm, models = client_with({"principal": ['{"value": "x"}', '{"value": 4}']})
    assert (await llm.structured(system="s", prompt="p", schema=Out)).value == 4
    assert models.calls == ["principal", "principal"]


async def test_modelo_saturado_pasa_al_de_respaldo() -> None:
    llm, models = client_with({"principal": [busy()], "respaldo": ['{"value": 5}']})
    assert (await llm.structured(system="s", prompt="p", schema=Out)).value == 5
    assert models.calls == ["principal", "respaldo"]


async def test_tiempo_agotado_pasa_al_de_respaldo() -> None:
    llm, models = client_with(
        {"principal": ["SLOW"], "respaldo": ['{"value": 6}']}, timeout_seconds=0.01
    )
    assert (await llm.structured(system="s", prompt="p", schema=Out)).value == 6
    assert models.calls == ["principal", "respaldo"]


async def test_si_ninguno_responde_bien_lanza_llm_unavailable() -> None:
    llm, _ = client_with({"principal": [busy()], "respaldo": ["no es json", "{}"]})
    with pytest.raises(LLMUnavailable):
        await llm.structured(system="s", prompt="p", schema=Out)


async def test_error_de_configuracion_no_se_esconde() -> None:
    bad_key = errors.ClientError(400, {"error": {"code": 400, "status": "INVALID_ARGUMENT"}})
    llm, models = client_with({"principal": [bad_key], "respaldo": ['{"value": 1}']})
    with pytest.raises(errors.ClientError):
        await llm.structured(system="s", prompt="p", schema=Out)
    assert models.calls == ["principal"]


async def test_envia_el_json_schema_completo() -> None:
    """`response_schema` de google-genai rechaza `exclusiveMinimum` (Field(gt=0))."""
    llm, models = client_with({"principal": ['{"intent": "other", "confidence": 1}']})
    await llm.structured(system="s", prompt="p", schema=Extraction)
    config = models.configs[0]
    assert config.response_schema is None
    assert config.response_json_schema == Extraction.model_json_schema()
