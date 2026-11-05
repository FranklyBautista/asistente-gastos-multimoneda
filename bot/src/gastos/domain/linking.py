"""Códigos para vincular la cuenta de Telegram con la web (Fase 9, ADR 0012)."""

import secrets
from collections.abc import Callable
from datetime import timedelta

# Sin I, O, 0 ni 1: se confunden al copiarlos a mano. Debe coincidir con el check de
# link_codes.code en la migración.
ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
CODE_LENGTH = 8
LINK_TTL = timedelta(minutes=10)


def new_code(choice: Callable[[str], str] = secrets.choice) -> str:
    """Código aleatorio de un solo uso (32^8 ≈ 10^12 combinaciones, vence en 10 minutos)."""
    return "".join(choice(ALPHABET) for _ in range(CODE_LENGTH))
