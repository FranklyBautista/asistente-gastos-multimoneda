"""Puntuación del set de evaluación (`bot/eval/dataset.jsonl`): extracción contra lo esperado.

Cada caso dice qué debería devolver el extractor; aquí se compara campo por campo y se
agregan las métricas. Es código puro: `bot/eval/run_eval.py` llama al LLM real y usa esto.

La moneda se evalúa como la usa el bot: si viene null o con confianza menor a 0.8, el bot
pregunta. Por eso un caso con `"currency": null` espera que el bot pregunte, y uno con moneda
espera que la anote sin preguntar.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Final

from gastos.domain.transaction import MIN_CURRENCY_CONFIDENCE
from gastos.extraction.schema import Extraction, ParsedTransaction

# Orden en que se muestran las métricas.
CHECKS: Final = (
    "intención",
    "cantidad de movimientos",
    "tipo",
    "monto",
    "moneda",
    "moneda clara anotada",
    "moneda dudosa preguntada",
    "categoría",
    "fecha",
    "cambio",
    "consulta",
    "corrección",
)


@dataclass(frozen=True, slots=True)
class CaseResult:
    case_id: str
    checks: dict[str, list[bool]] = field(default_factory=dict[str, list[bool]])
    failed: list[str] = field(default_factory=list[str])  # "monto: esperaba 20000, vino 20"

    @property
    def passed(self) -> bool:
        return not self.failed

    def check(self, name: str, ok: bool, detail: str) -> None:
        self.checks.setdefault(name, []).append(ok)
        if not ok:
            self.failed.append(f"{name}: {detail}")


def _decimal(value: Any) -> Decimal | None:
    return None if value is None else Decimal(str(value))


def _currency(tx: ParsedTransaction) -> str | None:
    """La moneda que anotaría el bot sin preguntar; None si preguntaría."""
    if tx.currency is None or tx.currency_confidence < MIN_CURRENCY_CONFIDENCE:
        return None
    return tx.currency


def _same_text(expected: Any, got: Any) -> bool:
    if isinstance(expected, str) and isinstance(got, str):
        return expected.strip().casefold() == got.strip().casefold()
    return expected == got


def _compare_fields(
    result: CaseResult, name: str, expected: Mapping[str, Any], got: Mapping[str, Any] | None
) -> None:
    """Compara solo los campos que el caso indica; los números por valor."""
    if got is None:
        result.check(name, False, "no vino")
        return
    for key, want in expected.items():
        have = got.get(key)
        if isinstance(want, int | float) and not isinstance(want, bool):
            ok = _decimal(have) == _decimal(want)
        elif key == "target_hint" and isinstance(want, str):
            ok = isinstance(have, str) and want.casefold() in have.casefold()
        else:
            ok = _same_text(want, have)
        result.check(name, ok, f"{key} esperaba {want!r}, vino {have!r}")


def _score_transactions(
    result: CaseResult,
    expected: list[Mapping[str, Any]],
    got: list[ParsedTransaction],
    now_local: datetime,
) -> None:
    result.check(
        "cantidad de movimientos",
        len(got) == len(expected),
        f"esperaba {len(expected)}, vinieron {len(got)}",
    )
    for i, want in enumerate(expected):
        tx = got[i] if i < len(got) else None
        label = f"#{i + 1}"
        if tx is None:
            for name in ("tipo", "monto", "moneda"):
                result.check(name, False, f"{label} no vino")
            continue
        result.check("tipo", tx.kind == want["kind"], f"{label} vino {tx.kind}")
        amount_ok = Decimal(str(tx.amount)) == Decimal(str(want["amount"]))
        result.check("monto", amount_ok, f"{label} esperaba {want['amount']}, vino {tx.amount}")
        currency = _currency(tx)
        currency_ok = currency == want["currency"]
        detail = f"{label} esperaba {want['currency']}, vino {currency} ({tx.currency_confidence})"
        result.check("moneda", currency_ok, detail)
        bucket = "moneda dudosa preguntada" if want["currency"] is None else "moneda clara anotada"
        result.check(bucket, currency_ok, detail)
        if "category" in want:
            result.check(
                "categoría",
                _same_text(want["category"], tx.category),
                f"{label} esperaba {want['category']}, vino {tx.category}",
            )
        if "day_offset" in want:
            expected_day = (now_local + timedelta(days=want["day_offset"])).date()
            day = datetime.fromisoformat(tx.occurred_at).date() if tx.occurred_at else None
            day = day or now_local.date()
            result.check(
                "fecha", day == expected_day, f"{label} esperaba {expected_day}, vino {day}"
            )


def score_case(case: Mapping[str, Any], extraction: Extraction, now_local: datetime) -> CaseResult:
    """Compara una extracción con lo que el caso espera."""
    result = CaseResult(str(case["id"]))
    intent = case["intent"]
    result.check(
        "intención", extraction.intent == intent, f"esperaba {intent}, vino {extraction.intent}"
    )
    if intent == "log_transactions":
        _score_transactions(
            result, case.get("transactions", []), extraction.transactions, now_local
        )
    for key, name in (("exchange", "cambio"), ("query", "consulta"), ("correction", "corrección")):
        if key in case:
            parsed = getattr(extraction, key)
            got = parsed.model_dump() if parsed is not None else None
            _compare_fields(result, name, case[key], got)
    return result


@dataclass(frozen=True, slots=True)
class Metric:
    name: str
    passed: int
    total: int

    @property
    def rate(self) -> float:
        return self.passed / self.total if self.total else 0.0


def summarize(results: Iterable[CaseResult]) -> tuple[list[Metric], Metric]:
    """Precisión por tipo de comprobación y casos completamente correctos."""
    results = list(results)
    totals: dict[str, list[bool]] = {}
    for r in results:
        for name, oks in r.checks.items():
            totals.setdefault(name, []).extend(oks)
    metrics = [Metric(n, sum(totals[n]), len(totals[n])) for n in CHECKS if n in totals]
    exact = Metric("casos exactos", sum(r.passed for r in results), len(results))
    return metrics, exact
