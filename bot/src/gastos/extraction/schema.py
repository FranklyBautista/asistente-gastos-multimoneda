"""Esquema de salida del LLM (sección Diseño técnico). Lo que no valide no se guarda.

Un cambio de moneda (`log_exchange`) llega en `exchange`, no en `transactions`: no es
gasto ni ingreso.
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from gastos.domain.periods import Period

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


class ParsedExchange(LLMOutput):
    from_currency: Currency | None = Field(
        default=None, description="La moneda que entregó; null si no se dice"
    )
    to_currency: Currency | None = Field(
        default=None, description="La moneda que recibió; null si no se dice"
    )
    from_amount: float | None = Field(default=None, gt=0, description="Cuánto entregó")
    to_amount: float | None = Field(default=None, gt=0, description="Cuánto recibió")
    rate: float | None = Field(
        default=None, gt=0, description='La tasa tal como la dijo ("a 985" -> 985)'
    )
    from_account_hint: str | None = Field(default=None, description="Cuenta de la que salió")
    to_account_hint: str | None = Field(default=None, description="Cuenta a la que entró")
    occurred_at: str | None = Field(
        default=None, description="ISO 8601 con hora local; null = ahora"
    )


class ParsedQuery(LLMOutput):
    """Una pregunta sobre sus finanzas: qué herramienta usar y con qué parámetros."""

    tool: Literal["spending_by_category", "totals", "account_balances", "list_transactions"]
    period: Period | None = Field(
        default=None, description='Periodo de la lista; "month" con month para un mes concreto'
    )
    month: int | None = Field(default=None, ge=1, le=12, description="Solo con period month")
    year: int | None = Field(default=None, ge=2000, le=2100, description="Solo si lo dice")
    kind: Literal["expense", "income"] | None = Field(
        default=None, description="Gastos o ingresos (totals y list_transactions)"
    )
    currency: Currency | None = Field(default=None, description="Solo si pregunta por una")
    category: str | None = Field(default=None, description="Solo si pregunta por una")
    in_usd: bool = Field(default=False, description="true solo si pide el total en dólares")
    limit: int | None = Field(
        default=None, ge=1, le=20, description="Cuántos movimientos (list_transactions)"
    )


class ParsedCorrection(LLMOutput):
    """Lo que cambia del último movimiento ("eso fue transporte", "eran 20 mil pesos")."""

    category: str | None = Field(default=None, description="Nueva categoría, si la dice")
    currency: Currency | None = Field(default=None, description="Nueva moneda, si la dice")
    amount: float | None = Field(default=None, gt=0, description="Nuevo monto, si lo dice")
    kind: Literal["expense", "income"] | None = Field(
        default=None, description="Solo si dice que era gasto o ingreso"
    )
    account_hint: str | None = Field(default=None, description="Nueva cuenta, si la dice")
    target_hint: str | None = Field(
        default=None, description='Qué movimiento corrige, si lo dice ("el café")'
    )


class Clarification(LLMOutput):
    field: Literal["currency", "amount", "account", "kind"]
    question: str = Field(description="En español, una línea")


class Extraction(LLMOutput):
    intent: Literal["log_transactions", "log_exchange", "query", "correction", "other"]
    transactions: list[ParsedTransaction] = Field(
        default_factory=list, description="Vacío si intent no es log_transactions"
    )
    query: ParsedQuery | None = Field(default=None, description="Solo con intent query")
    exchange: ParsedExchange | None = Field(
        default=None, description="Solo con intent log_exchange"
    )
    correction: ParsedCorrection | None = Field(
        default=None, description="Solo con intent correction"
    )
    clarification: Clarification | None = None
    confidence: float = Field(ge=0, le=1)
