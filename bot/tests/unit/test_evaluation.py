"""Puntuación del set de evaluación, y que el dataset sea válido."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from gastos.extraction.evaluation import CHECKS, score_case, summarize
from gastos.extraction.schema import Extraction

NOW = datetime(2026, 11, 2, 15, tzinfo=ZoneInfo("America/Caracas"))
DATASET = Path(__file__).parents[2] / "eval" / "dataset.jsonl"


def extraction(**fields: Any) -> Extraction:
    return Extraction.model_validate({"confidence": 0.9, **fields})


def tx(**fields: Any) -> dict[str, Any]:
    base = {"kind": "expense", "currency_confidence": 0.95, "description": "algo"}
    return base | fields


def test_caso_correcto() -> None:
    case = {
        "id": "ves-01",
        "intent": "log_transactions",
        "transactions": [
            {"kind": "expense", "amount": 70, "currency": "VES", "category": "transporte"}
        ],
    }
    got = extraction(
        intent="log_transactions",
        transactions=[tx(amount=70.0, currency="VES", category="transporte")],
    )
    result = score_case(case, got, NOW)
    assert result.passed
    assert result.checks["moneda clara anotada"] == [True]


def test_moneda_con_poca_confianza_cuenta_como_pregunta() -> None:
    case = {
        "id": "amb-03",
        "intent": "log_transactions",
        "transactions": [{"kind": "expense", "amount": 20000, "currency": None}],
    }
    asked = extraction(
        intent="log_transactions",
        transactions=[tx(amount=20000, currency="COP", currency_confidence=0.6)],
    )
    assert score_case(case, asked, NOW).passed  # el bot preguntaría: bien
    guessed = extraction(
        intent="log_transactions",
        transactions=[tx(amount=20000, currency="COP", currency_confidence=0.9)],
    )
    result = score_case(case, guessed, NOW)
    assert result.checks["moneda dudosa preguntada"] == [False]
    assert result.failed[0] == "moneda: #1 esperaba None, vino COP (0.9)"


def test_movimiento_faltante_y_monto_mal_leido() -> None:
    case = {
        "id": "multi",
        "intent": "log_transactions",
        "transactions": [
            {"kind": "expense", "amount": 15, "currency": "USD"},
            {"kind": "expense", "amount": 3, "currency": "USD"},
        ],
    }
    got = extraction(intent="log_transactions", transactions=[tx(amount=1.5, currency="USD")])
    result = score_case(case, got, NOW)
    assert result.checks["cantidad de movimientos"] == [False]
    assert result.checks["monto"] == [False, False]


def test_fecha_relativa() -> None:
    case = {
        "id": "ayer",
        "intent": "log_transactions",
        "transactions": [{"kind": "expense", "amount": 30, "currency": "VES", "day_offset": -1}],
    }
    yesterday = extraction(
        intent="log_transactions",
        transactions=[tx(amount=30, currency="VES", occurred_at="2026-11-01T12:00:00")],
    )
    assert score_case(case, yesterday, NOW).passed
    today = extraction(intent="log_transactions", transactions=[tx(amount=30, currency="VES")])
    assert score_case(case, today, NOW).checks["fecha"] == [False]


def test_cambio_consulta_y_correccion_solo_comparan_lo_indicado() -> None:
    exchange_case = {
        "id": "ex",
        "intent": "log_exchange",
        "exchange": {"from_currency": "USDT", "from_amount": 50, "rate": 985},
    }
    got = extraction(
        intent="log_exchange",
        exchange={"from_currency": "USDT", "to_currency": "VES", "from_amount": 50.0, "rate": 985},
    )
    assert score_case(exchange_case, got, NOW).passed
    query_case = {"id": "q", "intent": "query", "query": {"tool": "totals", "period": "today"}}
    wrong = extraction(intent="query", query={"tool": "totals", "period": "yesterday"})
    assert score_case(query_case, wrong, NOW).checks["consulta"] == [True, False]
    fix_case = {"id": "f", "intent": "correction", "correction": {"target_hint": "café"}}
    fix = extraction(intent="correction", correction={"currency": "VES", "target_hint": "el Café"})
    assert score_case(fix_case, fix, NOW).passed
    missing = extraction(intent="correction")
    assert score_case(fix_case, missing, NOW).failed == ["corrección: no vino"]


def test_resumen_por_comprobacion() -> None:
    good = score_case({"id": "a", "intent": "other"}, extraction(intent="other"), NOW)
    bad = score_case({"id": "b", "intent": "other"}, extraction(intent="query"), NOW)
    metrics, exact = summarize([good, bad])
    assert [(m.name, m.passed, m.total) for m in metrics] == [("intención", 1, 2)]
    assert (exact.passed, exact.total, exact.rate) == (1, 2, 0.5)


def _cases() -> list[dict[str, Any]]:
    return [json.loads(line) for line in DATASET.read_text(encoding="utf-8").splitlines()]


def test_el_dataset_es_valido() -> None:
    cases = _cases()
    ids = [c["id"] for c in cases]
    assert len(ids) == len(set(ids)), "ids repetidos"
    assert len(cases) >= 50
    ambiguous = [t for c in cases for t in c.get("transactions", []) if t["currency"] is None]
    assert len(ambiguous) >= 15  # el plan pide muchas frases con moneda dudosa


@pytest.mark.parametrize("case", _cases(), ids=lambda c: c["id"])
def test_cada_caso_se_puede_puntuar(case: dict[str, Any]) -> None:
    # Una extracción vacía con la intención correcta no debe romper el puntuador.
    result = score_case(case, extraction(intent=case["intent"]), NOW)
    assert set(result.checks) <= set(CHECKS)
    for t in case.get("transactions", []):
        assert t["kind"] in ("expense", "income")
        assert t["currency"] in ("VES", "COP", "USD", "USDT", None)
