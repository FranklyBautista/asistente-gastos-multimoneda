"""Comprobar que un texto redactado por el LLM no trae cifras que no le dimos.

Se extraen todos los números del texto y cada uno debe valer lo mismo que alguno de los
números permitidos (los de las métricas, ya formateados). Se compara por valor y no por texto
para aceptar "1.200" donde la métrica decía "1.200,00", pero no "1.250".
"""

import re
from collections.abc import Iterable
from decimal import Decimal, InvalidOperation
from typing import Final

_NUMBER: Final = re.compile(r"\d+(?:[.,]\d+)*")
_THOUSANDS: Final = re.compile(r"\d{1,3}(?:\.\d{3})*")


def numbers_in(text: str) -> list[str]:
    """Los números tal como aparecen: "Gastaste 1.200,50 Bs (12 %)" → ["1.200,50", "12"]."""
    return _NUMBER.findall(text)


def parse_local_number(token: str) -> Decimal | None:
    """Lee un número escrito a la venezolana: punto de miles y coma decimal.

    Devuelve None si no tiene esa forma ("1.2" no es un número de miles válido).
    """
    integer, _, decimals = token.partition(",")
    if "," in decimals:
        return None
    if "." in integer:
        if not _THOUSANDS.fullmatch(integer):
            return None
        integer = integer.replace(".", "")
    try:
        return Decimal(f"{integer}.{decimals}" if decimals else integer)
    except InvalidOperation:
        return None


def unknown_numbers(text: str, allowed: Iterable[str]) -> list[str]:
    """Los números de `text` que no coinciden con ninguno de los textos de `allowed`."""
    allowed_raw: set[str] = set()
    allowed_values: set[Decimal] = set()
    for item in allowed:
        for token in numbers_in(item):
            allowed_raw.add(token)
            value = parse_local_number(token)
            if value is not None:
                allowed_values.add(value)
    unknown: list[str] = []
    for token in numbers_in(text):
        if token in allowed_raw:
            continue
        value = parse_local_number(token)
        if value is None or value not in allowed_values:
            unknown.append(token)
    return unknown
