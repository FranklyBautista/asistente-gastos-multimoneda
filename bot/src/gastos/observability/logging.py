"""Configuración de logs: JSON en producción y legible en desarrollo.

Regla: en INFO solo ids y tipos de evento; nunca el texto de los mensajes ni montos.
"""

import logging
import sys
from typing import Literal

import structlog


def configure_logging(env: Literal["dev", "prod"], level: int = logging.INFO) -> None:
    renderer: structlog.typing.Processor = (
        structlog.processors.JSONRenderer()
        if env == "prod"
        else structlog.dev.ConsoleRenderer(colors=sys.stderr.isatty())
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(sys.stderr),
        cache_logger_on_first_use=True,
    )
    # Los logs propios de aiogram y psycopg van por logging estándar.
    logging.basicConfig(
        level=logging.WARNING, stream=sys.stderr, format="%(levelname)s %(name)s: %(message)s"
    )
