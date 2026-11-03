"""Mide la extracción real (Gemini) con las frases de `dataset.jsonl`.

Uso, desde bot/ (necesita GEMINI_API_KEY en bot/.env; no toca la base de datos):

    uv run python eval/run_eval.py              # todo el set
    uv run python eval/run_eval.py --only amb-  # solo los casos cuyo id empieza así
    uv run python eval/run_eval.py --delay 6    # más pausa si el plan gratuito da 429

Consume una llamada al LLM por frase, así que no corre en el CI: se ejecuta a mano cuando
cambia el prompt. El resultado se guarda en `eval/results/<versión del prompt>.json`.
"""

import argparse
import asyncio
import json
import logging
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from gastos.config import get_settings
from gastos.domain.errors import LLMUnavailable
from gastos.extraction.evaluation import CaseResult, score_case, summarize
from gastos.extraction.parser import Categories, Extractor
from gastos.extraction.prompt import PROMPT_VERSION
from gastos.main import build_llm
from gastos.observability.logging import configure_logging

HERE = Path(__file__).parent
# Las categorías globales del seed (supabase/migrations/..._init_schema.sql).
CATEGORIES = Categories(
    expense=["comida", "otros", "ocio", "salud", "servicios", "transporte"],
    income=["otros ingresos", "salario"],
)


def load(only: str | None) -> list[dict[str, Any]]:
    lines = (HERE / "dataset.jsonl").read_text(encoding="utf-8").splitlines()
    cases = [json.loads(line) for line in lines if line.strip()]
    return [c for c in cases if not only or str(c["id"]).startswith(only)]


async def run(cases: list[dict[str, Any]], delay: float) -> tuple[list[CaseResult], list[str]]:
    settings = get_settings()
    configure_logging(settings.env, level=logging.WARNING)  # solo avisos (429, reintentos)
    extractor = Extractor(build_llm(settings))
    now_local = datetime.now(ZoneInfo("America/Caracas"))
    results: list[CaseResult] = []
    errors: list[str] = []
    for i, case in enumerate(cases, start=1):
        try:
            extraction = await extractor.extract(case["text"], CATEGORIES, now_local)
        except LLMUnavailable:
            errors.append(case["id"])
            print(f"[{i}/{len(cases)}] {case['id']}: el LLM no respondió", flush=True)
            continue
        result = score_case(case, extraction, now_local)
        results.append(result)
        mark = "ok" if result.passed else "FALLA"
        print(f"[{i}/{len(cases)}] {case['id']}: {mark}", flush=True)
        for failure in result.failed:
            print(f"    {failure}", flush=True)
        if i < len(cases):
            await asyncio.sleep(delay)  # el plan gratuito limita las llamadas por minuto
    return results, errors


def report(
    cases: list[dict[str, Any]], results: list[CaseResult], errors: list[str], seconds: float
) -> dict[str, Any]:
    metrics, exact = summarize(results)
    print(f"\nPrompt {PROMPT_VERSION} · {len(results)} frases evaluadas · {seconds:.0f} s")
    for m in [*metrics, exact]:
        print(f"  {m.name:<26} {m.rate:7.1%}  ({m.passed}/{m.total})")
    if errors:
        print(f"  Sin respuesta del LLM: {', '.join(errors)}")
    texts = {c["id"]: c["text"] for c in cases}
    return {
        "prompt_version": PROMPT_VERSION,
        "models": get_settings().gemini_models,
        "date": datetime.now(UTC).isoformat(timespec="seconds"),
        "cases": len(results),
        "llm_errors": errors,
        "metrics": {m.name: {"passed": m.passed, "total": m.total} for m in metrics},
        "exact": {"passed": exact.passed, "total": exact.total},
        "failures": [
            {"id": r.case_id, "text": texts[r.case_id], "failed": r.failed}
            for r in results
            if not r.passed
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--only", help="prefijo de id de los casos a correr")
    parser.add_argument("--delay", type=float, default=4.0, help="segundos entre llamadas")
    args = parser.parse_args()

    cases = load(args.only)
    started = time.perf_counter()
    loop_factory = asyncio.SelectorEventLoop if sys.platform == "win32" else None
    results, errors = asyncio.run(run(cases, args.delay), loop_factory=loop_factory)
    summary = report(cases, results, errors, time.perf_counter() - started)
    if args.only:
        return  # un subconjunto no reemplaza el resultado guardado del set completo
    out = HERE / "results" / f"{PROMPT_VERSION}.json"
    out.parent.mkdir(exist_ok=True)
    text = json.dumps(summary, ensure_ascii=False, indent=2) + "\n"
    out.write_text(text, encoding="utf-8", newline="\n")  # LF también en Windows
    print(f"\nGuardado en {out.relative_to(HERE.parent)}")


if __name__ == "__main__":
    main()
