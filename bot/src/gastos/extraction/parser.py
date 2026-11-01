"""Convierte un mensaje en una `Extraction` validada y la pasa a borradores de dominio."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

import structlog

from gastos.domain.exchange import ExchangeDraft
from gastos.domain.transaction import TransactionDraft
from gastos.extraction.prompt import PROMPT_VERSION, system_prompt, user_prompt
from gastos.extraction.schema import Extraction, ParsedExchange, ParsedTransaction
from gastos.llm.base import LLMClient

log = structlog.get_logger()


@dataclass(frozen=True, slots=True)
class Categories:
    expense: Sequence[str]
    income: Sequence[str]


class Extractor:
    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    async def extract(
        self,
        text: str,
        categories: Categories,
        now_local: datetime,
        previous: tuple[str, str] | None = None,
    ) -> Extraction:
        """`previous` = (mensaje anterior, pregunta del bot) si `text` responde a esa pregunta."""
        extraction = await self._llm.structured(
            system=system_prompt(categories.expense, categories.income, now_local),
            prompt=user_prompt(text, previous),
            schema=Extraction,
        )
        log.info(
            "message_extracted",
            prompt_version=PROMPT_VERSION,
            intent=extraction.intent,
            transactions=len(extraction.transactions),
            exchange=extraction.exchange is not None,
            followup=previous is not None,
            confidence=extraction.confidence,
        )
        return extraction


def to_drafts(
    parsed: Sequence[ParsedTransaction], categories: Categories, now_local: datetime
) -> list[TransactionDraft]:
    """Pasa la salida del LLM al dominio: montos a Decimal, fechas con zona y categorías válidas.

    Una categoría que no está en la lista se descarta (el servicio usa la de respaldo) y una
    fecha futura o ilegible se toma como "ahora".
    """
    drafts: list[TransactionDraft] = []
    for item in parsed:
        valid = categories.expense if item.kind == "expense" else categories.income
        drafts.append(
            TransactionDraft(
                kind=item.kind,
                amount=_to_decimal(item.amount),
                currency=item.currency,
                currency_confidence=item.currency_confidence,
                description=item.description.strip()[:200] or "sin descripción",
                category=item.category if item.category in valid else None,
                account_hint=item.account_hint,
                occurred_at=_parse_occurred_at(item.occurred_at, now_local),
            )
        )
    return drafts


def to_exchange_draft(parsed: ParsedExchange, now_local: datetime) -> ExchangeDraft:
    return ExchangeDraft(
        from_currency=parsed.from_currency,
        to_currency=parsed.to_currency,
        from_amount=_optional_decimal(parsed.from_amount),
        to_amount=_optional_decimal(parsed.to_amount),
        quoted_rate=None if parsed.rate is None else _exact_decimal(parsed.rate),
        from_account_hint=parsed.from_account_hint,
        to_account_hint=parsed.to_account_hint,
        occurred_at=_parse_occurred_at(parsed.occurred_at, now_local),
    )


def _exact_decimal(value: float) -> Decimal:
    """El LLM entrega float; se pasa por str para no arrastrar errores binarios (0.1 → 0.1)."""
    try:
        return Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError(f"número inválido: {value}") from exc


def _to_decimal(value: float) -> Decimal:
    """Monto a la escala de la base de datos (numeric(20,6))."""
    return _exact_decimal(value).quantize(Decimal("1e-6"))


def _optional_decimal(value: float | None) -> Decimal | None:
    return None if value is None else _to_decimal(value)


def _parse_occurred_at(value: str | None, now_local: datetime) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        log.warning("llm_bad_date", value=value)
        return None
    if parsed.tzinfo is None:
        tz = now_local.tzinfo or ZoneInfo("UTC")
        parsed = parsed.replace(tzinfo=tz)
    return None if parsed > now_local else parsed
