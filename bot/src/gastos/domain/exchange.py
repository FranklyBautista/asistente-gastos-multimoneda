"""Cambios entre monedas: completar el dato que falta y compararlo con la tasa de referencia.

Convención (como `exchanges.effective_rate`): una tasa de cambio son las unidades de la
moneda recibida por 1 de la entregada (`to_amount / from_amount`).
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_EVEN, Decimal
from uuid import UUID

from gastos.domain.account import Account
from gastos.domain.conversion import RATE_SCALE, USD_SCALE
from gastos.domain.currency import Currency

PERCENT_SCALE = Decimal("0.01")


@dataclass(frozen=True, slots=True)
class ExchangeDraft:
    """Un cambio entendido del texto; puede faltarle una moneda o alguno de los tres datos."""

    from_currency: Currency | None
    to_currency: Currency | None
    from_amount: Decimal | None
    to_amount: Decimal | None
    quoted_rate: Decimal | None  # tal como la dijo el usuario; la dirección se decide después
    from_account_hint: str | None = None
    to_account_hint: str | None = None
    occurred_at: datetime | None = None

    def __post_init__(self) -> None:
        for name in ("from_amount", "to_amount", "quoted_rate"):
            value: Decimal | None = getattr(self, name)
            if value is not None and not (value.is_finite() and value > 0):
                raise ValueError(f"{name} debe ser positivo: {value}")
        if self.occurred_at is not None and self.occurred_at.tzinfo is None:
            raise ValueError("occurred_at debe llevar zona horaria")


@dataclass(frozen=True, slots=True)
class ExchangeAmounts:
    from_amount: Decimal
    to_amount: Decimal
    effective_rate: Decimal  # to_amount / from_amount


def reference_rate(from_usd_per_unit: Decimal, to_usd_per_unit: Decimal) -> Decimal:
    """La tasa de referencia en la dirección del cambio: unidades de destino por 1 de origen."""
    return (from_usd_per_unit / to_usd_per_unit).quantize(RATE_SCALE, rounding=ROUND_HALF_EVEN)


def is_inverted(quoted: Decimal, reference: Decimal | None) -> bool:
    """True si la tasa dicha está en "origen por 1 de destino" y hay que darle la vuelta.

    Quien vende 50 USDT "a 985" y quien compra 50 USDT "a 985" dicen la misma tasa en las dos
    direcciones: siempre se cotiza la moneda débil por la fuerte. Se elige la orientación más
    cercana a la tasa de referencia; sin referencia, se toma tal cual.
    """
    if reference is None:
        return False
    distance = abs((quoted / reference).ln())
    inverse_distance = abs((1 / (quoted * reference)).ln())
    return inverse_distance < distance


def complete_amounts(
    from_amount: Decimal | None,
    to_amount: Decimal | None,
    quoted_rate: Decimal | None,
    reference: Decimal | None,
) -> ExchangeAmounts | None:
    """Calcula el dato que falta a partir de los otros dos; None si se conoce menos de dos.

    Si están los tres, mandan los montos: la tasa dicha suele estar redondeada. La cuenta se
    hace con la tasa tal como se dijo (sin invertirla ni redondearla antes) y la tasa efectiva
    sale siempre de los montos.
    """
    if from_amount is None or to_amount is None:
        if quoted_rate is None:
            return None
        inverted = is_inverted(quoted_rate, reference)
        if from_amount is not None:
            to_amount = _amount(
                from_amount / quoted_rate if inverted else from_amount * quoted_rate
            )
        elif to_amount is not None:
            from_amount = _amount(to_amount * quoted_rate if inverted else to_amount / quoted_rate)
        else:
            return None
    return ExchangeAmounts(from_amount, to_amount, _rate(to_amount / from_amount))


def difference_pct(effective: Decimal, reference: Decimal) -> Decimal:
    """Cuánto más (positivo) o menos (negativo) recibiste que con la tasa de referencia."""
    return ((effective / reference - 1) * 100).quantize(PERCENT_SCALE, rounding=ROUND_HALF_EVEN)


def _rate(value: Decimal) -> Decimal:
    return value.quantize(RATE_SCALE, rounding=ROUND_HALF_EVEN)


def _amount(value: Decimal) -> Decimal:
    return value.quantize(USD_SCALE, rounding=ROUND_HALF_EVEN)


@dataclass(frozen=True, slots=True)
class NewExchange:
    """Un cambio listo para guardar: con cuentas, montos completos y tasa de referencia."""

    from_account: Account
    to_account: Account
    amounts: ExchangeAmounts
    reference_rate: Decimal | None
    occurred_at: datetime | None
    raw_text: str


@dataclass(frozen=True, slots=True)
class SavedExchange:
    id: UUID
    from_currency: Currency
    to_currency: Currency
    amounts: ExchangeAmounts
    reference_rate: Decimal | None
    from_account_name: str
    to_account_name: str
    occurred_at: datetime
