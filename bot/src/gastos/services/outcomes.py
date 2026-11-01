"""Resultados compartidos por los casos de uso de mensajes; el chat los convierte en texto."""

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class Ask:
    """Falta un dato: el bot pregunta y la próxima respuesta completa el mensaje anterior."""

    question: str


@dataclass(frozen=True, slots=True)
class NotATransaction:
    """Se entendió, pero no es algo que el bot registre (todavía)."""

    intent: Literal["query", "correction", "transfer", "other"]
