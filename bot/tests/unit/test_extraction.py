"""Esquema, prompt y paso de la salida del LLM al dominio."""

import json
import re
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from gastos.domain.transaction import TransactionDraft
from gastos.extraction import prompt
from gastos.extraction.parser import Categories, Extractor, to_drafts
from gastos.extraction.schema import Extraction, ParsedTransaction
from tests.fakes import FakeLLM

CARACAS = ZoneInfo("America/Caracas")
NOW = datetime(2026, 10, 31, 15, 30, tzinfo=CARACAS)
CATEGORIES = Categories(
    expense=["comida", "transporte", "ocio", "salud", "otros"],
    income=["salario", "otros ingresos"],
)


def parsed(**overrides: object) -> ParsedTransaction:
    data: dict[str, object] = {
        "kind": "expense",
        "amount": 15,
        "currency": "VES",
        "currency_confidence": 0.95,
        "category": "comida",
        "description": "almuerzo",
    }
    return ParsedTransaction.model_validate(data | overrides)


def test_los_ejemplos_del_prompt_cumplen_el_esquema() -> None:
    """Un ejemplo few-shot que no valida le enseña al LLM a fallar."""
    examples = re.findall(r'^"(.+?)" ->\n(\{.*?\})\n(?:\n|$)', prompt._EXAMPLES, re.M | re.S)
    assert len(examples) >= 10
    for message, raw in examples:
        extraction = Extraction.model_validate(json.loads(raw))
        for tx in extraction.transactions:
            valid = CATEGORIES.expense if tx.kind == "expense" else CATEGORIES.income
            assert tx.category is None or tx.category in valid, message


def test_el_prompt_lleva_categorias_y_fecha_local() -> None:
    text = prompt.system_prompt(CATEGORIES.expense, CATEGORIES.income, NOW)
    assert "Categorías de gasto: comida, transporte, ocio, salud, otros." in text
    assert "Categorías de ingreso: salario, otros ingresos." in text
    assert "sábado 2026-10-31T15:30-04:00" in text


async def test_extractor_valida_la_respuesta_del_llm() -> None:
    llm = FakeLLM({"intent": "query", "confidence": 0.9})
    result = await Extractor(llm).extract("¿cuánto gasté?", CATEGORIES, NOW)
    assert result.intent == "query"
    assert result.transactions == []
    assert llm.calls[0][1] == "Mensaje: ¿cuánto gasté?"


def test_monto_pasa_a_decimal_exacto() -> None:
    [draft] = to_drafts([parsed(amount=7.99)], CATEGORIES, NOW)
    assert draft.amount == Decimal("7.99")


def test_categoria_inventada_o_de_otro_tipo_se_descarta() -> None:
    drafts = to_drafts(
        [parsed(category="mascotas"), parsed(kind="income", category="comida")], CATEGORIES, NOW
    )
    assert [d.category for d in drafts] == [None, None]


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, None),
        ("2026-10-30T12:00:00", datetime(2026, 10, 30, 12, tzinfo=CARACAS)),
        ("2026-11-02T12:00:00", None),  # futura → ahora
        ("ayer", None),  # ilegible → ahora
    ],
)
def test_fecha_en_la_zona_del_usuario(value: str | None, expected: datetime | None) -> None:
    [draft] = to_drafts([parsed(occurred_at=value)], CATEGORIES, NOW)
    assert draft.occurred_at == expected


@pytest.mark.parametrize(
    ("currency", "confidence", "needs"),
    [("VES", 0.95, False), ("COP", 0.8, False), ("COP", 0.6, True), (None, 0.0, True)],
)
def test_moneda_dudosa_se_pregunta(currency: str | None, confidence: float, needs: bool) -> None:
    [draft] = to_drafts(
        [parsed(currency=currency, currency_confidence=confidence)], CATEGORIES, NOW
    )
    assert draft.needs_currency is needs
    assert not draft.with_currency("USD").needs_currency


def test_borrador_rechaza_montos_no_positivos() -> None:
    with pytest.raises(ValueError):
        TransactionDraft("expense", Decimal(0), "USD", 1.0, "nada")


def test_el_llm_ve_todos_los_campos_como_obligatorios() -> None:
    """Gemini omite los campos fuera de `required`, incluido `transactions`."""
    schema = Extraction.model_json_schema()
    assert set(schema["required"]) == set(schema["properties"])
    for definition in schema["$defs"].values():
        assert set(definition["required"]) == set(definition["properties"])
    # Del lado de Python siguen siendo opcionales.
    assert Extraction.model_validate({"intent": "other", "confidence": 1}).transactions == []
