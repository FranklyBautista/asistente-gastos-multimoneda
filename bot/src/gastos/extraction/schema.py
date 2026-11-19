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

    tool: Literal[
        "spending_by_category",
        "totals",
        "account_balances",
        "list_transactions",
        "list_debts",
        "budget_status",
        "runway",
    ]
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
    direction: Literal["i_owe", "owed_to_me"] | None = Field(
        default=None, description="list_debts: lo que debe (i_owe) o lo que le deben; null = ambas"
    )
    counterparty: str | None = Field(
        default=None, description="list_debts: solo si pregunta por una persona"
    )
    include_settled: bool = Field(
        default=False, description="list_debts: true solo si pide también las ya pagadas"
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


DebtDirection = Literal["i_owe", "owed_to_me"]


class ParsedDebt(LLMOutput):
    """Una deuda nueva: "le debo 20 dólares a Miguel" o "Luisa me debe 50 mil"."""

    direction: DebtDirection = Field(
        description="i_owe si el usuario le debe a alguien; owed_to_me si alguien le debe a él"
    )
    counterparty: str = Field(description='La otra persona, tal como la escribió: "Miguel"')
    amount: float = Field(gt=0, description='Ya normalizado: "50 mil" -> 50000')
    currency: Currency | None = Field(
        default=None, description="null si el mensaje no deja clara la moneda"
    )
    currency_confidence: float = Field(ge=0, le=1)
    category: str | None = Field(
        default=None, description="Categoría de gasto de la lista según lo que fue, o null"
    )
    description: str | None = Field(
        default=None, description='Qué fue, en minúsculas ("almuerzo"); null si no lo dice'
    )


class ParsedDebtPayment(LLMOutput):
    """Un pago de una deuda: "le pagué 10 a Miguel" o "Luisa me pagó"."""

    direction: DebtDirection = Field(
        description="i_owe si el usuario pagó lo que debía; owed_to_me si le pagaron a él"
    )
    counterparty: str = Field(description="La otra persona, tal como la escribió")
    amount: float | None = Field(
        default=None, gt=0, description="null si no dice el monto (paga todo lo pendiente)"
    )
    currency: Currency | None = Field(default=None, description="Solo si la dice")
    account_hint: str | None = Field(
        default=None, description="Cuenta de donde salió o a donde entró el dinero, si la dice"
    )


class ParsedBudget(LLMOutput):
    """Un tope de gasto mensual: "no quiero gastar más de 100 dólares al mes en comida"."""

    category: str | None = Field(
        default=None,
        description="Categoría de gasto de la lista; si no existe, la palabra tal como la dijo",
    )
    amount: float | None = Field(
        default=None, gt=0, description="Máximo al mes; null si no lo dice"
    )
    currency: Currency | None = Field(default=None, description="Solo si la dice")
    remove: bool = Field(default=False, description="true solo si pide quitar el tope")


class Clarification(LLMOutput):
    field: Literal["currency", "amount", "account", "kind"]
    question: str = Field(description="En español, una línea")


class Extraction(LLMOutput):
    intent: Literal[
        "log_transactions",
        "log_exchange",
        "log_debt",
        "settle_debt",
        "set_budget",
        "query",
        "correction",
        "other",
    ]
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
    debt: ParsedDebt | None = Field(default=None, description="Solo con intent log_debt")
    debt_payment: ParsedDebtPayment | None = Field(
        default=None, description="Solo con intent settle_debt"
    )
    budget: ParsedBudget | None = Field(default=None, description="Solo con intent set_budget")
    clarification: Clarification | None = None
    confidence: float = Field(ge=0, le=1)
