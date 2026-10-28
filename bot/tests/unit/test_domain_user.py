import pytest

from gastos.domain.currency import parse_currency, parse_ves_rate_source
from gastos.domain.errors import InvalidPreference
from gastos.domain.user import parse_timezone


@pytest.mark.parametrize("code", ["VES", "COP", "USD", "USDT"])
def test_acepta_las_cuatro_monedas(code: str) -> None:
    assert parse_currency(code) == code


@pytest.mark.parametrize("code", ["usd", "VED", "EUR", ""])
def test_rechaza_monedas_desconocidas(code: str) -> None:
    with pytest.raises(InvalidPreference) as exc:
        parse_currency(code)
    assert exc.value.field == "currency"


def test_valida_la_fuente_de_bs() -> None:
    assert parse_ves_rate_source("p2p") == "p2p"
    with pytest.raises(InvalidPreference):
        parse_ves_rate_source("binance")


@pytest.mark.parametrize("name", ["America/Caracas", "America/Bogota", "UTC"])
def test_acepta_zonas_iana(name: str) -> None:
    assert parse_timezone(name) == name


@pytest.mark.parametrize("name", ["Caracas", "America/Narnia", "../etc/passwd", ""])
def test_rechaza_zonas_invalidas(name: str) -> None:
    with pytest.raises(InvalidPreference):
        parse_timezone(name)
