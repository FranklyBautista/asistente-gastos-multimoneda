"""Esquema de salida del LLM (sección Diseño técnico). Lo que no valide no se guarda.

`ParsedExchange` llega con la Fase 5; mientras tanto, la intención `log_exchange` basta
para no registrar un cambio de moneda como si fuera un gasto.
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

Currency = Literal["VES", "COP", "USD", "USDT"]


def _require_all(schema: dict[str, Any]) -> None:
    """En el JSON Schema que ve el LLM todos los campos son obligatorios (los opcionales, null).

    Gemini omite los campos que no están en `required`, incluido `transactions`. Del lado de
    Python los valores por defecto se conservan para validar respuestas y ejemplos cortos.
    """
    schema["required"] = list(schema.get("properties", {}))


class LLMOutput(BaseModel):
    model_config = ConfigDict(json_schema_extra=_require_all)


class ParsedTransaction(LLMOutput):
    kind: Literal["expense", "income"]
    amount: float = Field(gt=0, description='Ya normalizado: "20 mil" -> 20000')
    currency: Currency | None = Field(
        default=None, description="null si el mensaje no deja clara la moneda"
    )
    currency_confidence: float = Field(ge=0, le=1)
    category: str | None = Field(default=None, description="Nombre de una categoría de la lista")
    description: str = Field(description="Qué fue, en pocas palabras y en minúsculas")
    account_hint: str | None = Field(
        default=None, description='Cuenta mencionada: "banesco", "binance", "efectivo"'
    )
    occurred_at: str | None = Field(
        default=None, description="ISO 8601 con hora local; null = ahora"
    )


class Clarification(LLMOutput):
    field: Literal["currency", "amount", "account", "kind"]
    question: str = Field(description="En español, una línea")


class Extraction(LLMOutput):
    intent: Literal["log_transactions", "log_exchange", "query", "correction", "other"]
    transactions: list[ParsedTransaction] = Field(
        default_factory=list, description="Vacío si intent no es log_transactions"
    )
    clarification: Clarification | None = None
    confidence: float = Field(ge=0, le=1)
