"""Reglas puras de los cambios: completar el dato que falta, dirección de la tasa y diferencia."""

from decimal import Decimal

import pytest

from gastos.domain.exchange import (
    ExchangeAmounts,
    ExchangeDraft,
    complete_amounts,
    difference_pct,
    is_inverted,
    reference_rate,
)

D = Decimal
# 1 USDT = 0,999 USD y 1 Bs = 0,001 USD → 999 Bs por USDT.
USDT_TO_VES = reference_rate(D("0.999"), D("0.001"))
VES_TO_USDT = reference_rate(D("0.001"), D("0.999"))


def test_referencia_en_la_direccion_del_cambio() -> None:
    assert USDT_TO_VES == D("999.0000000000")
    assert VES_TO_USDT == D("0.0010010010")


@pytest.mark.parametrize(
    ("quoted", "reference", "inverted"),
    [
        (D(985), USDT_TO_VES, False),  # vendí USDT "a 985": ya está en Bs por USDT
        (D(985), VES_TO_USDT, True),  # compré USDT "a 985": hay que darle la vuelta
        (D("0.001015"), VES_TO_USDT, False),  # alguien que lo dijo al derecho
        (D(985), None, False),  # sin referencia se toma tal cual
        (D(1), D("0.9995"), False),  # USD ↔ USDT: las dos orientaciones valen casi igual
    ],
)
def test_direccion_de_la_tasa(quoted: Decimal, reference: Decimal | None, inverted: bool) -> None:
    assert is_inverted(quoted, reference) is inverted


def test_con_monto_entregado_y_tasa_calcula_lo_recibido() -> None:
    assert complete_amounts(D(50), None, D(985), USDT_TO_VES) == ExchangeAmounts(
        D(50), D("49250.000000"), D("985.0000000000")
    )


def test_compra_con_tasa_al_reves_sin_errores_de_redondeo() -> None:
    """20 USDT "a 990" pagados en Bs son 19.800 Bs exactos, no 19.800,000198."""
    amounts = complete_amounts(None, D(20), D(990), VES_TO_USDT)
    assert amounts is not None
    assert amounts.from_amount == D("19800.000000")
    assert amounts.effective_rate == D("0.0010101010")


def test_con_los_dos_montos_mandan_los_montos() -> None:
    amounts = complete_amounts(D(100), D(98500), D(990), None)
    assert amounts == ExchangeAmounts(D(100), D(98500), D("985.0000000000"))


@pytest.mark.parametrize(
    ("from_amount", "to_amount", "rate"),
    [(D(50), None, None), (None, D(50), None), (None, None, D(985)), (None, None, None)],
)
def test_con_menos_de_dos_datos_no_se_completa(
    from_amount: Decimal | None, to_amount: Decimal | None, rate: Decimal | None
) -> None:
    assert complete_amounts(from_amount, to_amount, rate, USDT_TO_VES) is None


def test_diferencia_contra_la_referencia() -> None:
    assert difference_pct(D(985), USDT_TO_VES) == D("-1.40")
    assert difference_pct(D(1010), D(1000)) == D("1.00")
    assert difference_pct(D(1000), D(1000)) == D("0.00")


def test_borrador_rechaza_montos_no_positivos() -> None:
    with pytest.raises(ValueError):
        ExchangeDraft("USDT", "VES", D(0), None, None)
