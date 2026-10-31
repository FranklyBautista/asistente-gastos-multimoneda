"""Errores de dominio: los handlers los traducen a mensajes claros para el usuario."""


class DomainError(Exception):
    """Base de los errores esperables (no son bugs)."""


class InvalidPreference(DomainError):
    """Un valor de preferencia del usuario que no está permitido."""

    def __init__(self, field: str, value: str) -> None:
        super().__init__(f"valor no permitido para {field}: {value!r}")
        self.field = field
        self.value = value


class RateUnavailable(DomainError):
    """No hay ninguna tasa guardada para esa moneda y fuente (ni siquiera una vieja)."""

    def __init__(self, currency: str, source: str) -> None:
        super().__init__(f"no hay tasa para {currency} ({source})")
        self.currency = currency
        self.source = source
