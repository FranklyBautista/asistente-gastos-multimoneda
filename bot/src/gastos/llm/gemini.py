"""Adaptador de Gemini (API de Google AI Studio) con salida estructurada.

- Cada modelo tiene un tiempo límite: un modelo saturado puede tardar minutos en responder.
- Si un modelo está saturado o sin cuota (429, 5xx o tiempo agotado), se pasa al siguiente.
- Si la salida no valida contra el esquema, se reintenta una vez con el mismo modelo.
"""

import asyncio
from collections.abc import Sequence

import structlog
from google import genai
from google.genai import errors, types
from pydantic import BaseModel, ValidationError

from gastos.domain.errors import LLMUnavailable

log = structlog.get_logger()

_TRANSIENT_CODES = frozenset({408, 429, 500, 502, 503, 504})


class GeminiClient:
    def __init__(
        self,
        api_key: str,
        models: Sequence[str],
        *,
        timeout_seconds: float = 20,
        client: genai.Client | None = None,  # las pruebas pasan uno falso
    ) -> None:
        if not models:
            raise ValueError("hace falta al menos un modelo de Gemini")
        self._client = client or genai.Client(api_key=api_key)
        self._models = tuple(models)
        self._timeout = timeout_seconds

    async def structured[T: BaseModel](self, *, system: str, prompt: str, schema: type[T]) -> T:
        config = types.GenerateContentConfig(
            system_instruction=system,
            response_mime_type="application/json",
            # JSON Schema completo: `response_schema` rechaza restricciones como exclusiveMinimum.
            response_json_schema=schema.model_json_schema(),
            temperature=0,
        )
        for model in self._models:
            for attempt in (1, 2):
                try:
                    response = await asyncio.wait_for(
                        self._client.aio.models.generate_content(
                            model=model, contents=prompt, config=config
                        ),
                        timeout=self._timeout,
                    )
                except TimeoutError:
                    log.warning("llm_unavailable", model=model, reason="timeout")
                    break
                except errors.APIError as exc:
                    if exc.code in _TRANSIENT_CODES:
                        log.warning("llm_unavailable", model=model, code=exc.code)
                        break
                    raise  # 400, 401, 403: error de configuración, no se arregla reintentando
                try:
                    return schema.model_validate_json(response.text or "")
                except ValidationError as exc:
                    log.warning(
                        "llm_invalid_output", model=model, attempt=attempt, errors=exc.error_count()
                    )
        raise LLMUnavailable("ningún modelo de Gemini devolvió una salida válida")
