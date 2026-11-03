"""Servidor HTTP de producción: recibe los updates de Telegram por webhook y expone /health.

Telegram espera respuesta rápida y reintenta si no la recibe; como un mensaje puede tardar
5–15 s por el LLM, el update se procesa en segundo plano y se responde 200 de inmediato.
"""

import asyncio
import hmac
import signal
from collections.abc import AsyncIterator, Awaitable, Callable, Generator
from contextlib import asynccontextmanager, contextmanager
from typing import Any, Protocol

import structlog
import uvicorn
from aiogram import Bot
from aiogram.types import Update
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from pydantic import ValidationError

log = structlog.get_logger()

WEBHOOK_PATH = "/telegram/webhook"
SECRET_HEADER = "X-Telegram-Bot-Api-Secret-Token"
# Tiempo para terminar los updates en curso al apagar (Railway manda SIGTERM al redesplegar).
DRAIN_SECONDS = 20

HealthCheck = Callable[[], Awaitable[bool]]


class UpdateFeeder(Protocol):
    async def feed_update(self, bot: Bot, update: Update, **kwargs: Any) -> Any: ...


class BackgroundUpdates:
    """Procesa cada update en su propia tarea y permite esperar a las pendientes al apagar."""

    def __init__(self, bot: Bot, dispatcher: UpdateFeeder) -> None:
        self._bot = bot
        self._dispatcher = dispatcher
        self._tasks: set[asyncio.Task[Any]] = set()

    @property
    def pending(self) -> int:
        return len(self._tasks)

    def submit(self, update: Update) -> None:
        task = asyncio.create_task(self._dispatcher.feed_update(self._bot, update))
        self._tasks.add(task)  # sin referencia, la tarea podría recolectarse a medias
        task.add_done_callback(self._finished)

    def _finished(self, task: asyncio.Task[Any]) -> None:
        self._tasks.discard(task)
        if not task.cancelled() and (exc := task.exception()) is not None:
            # Los errores de los handlers ya los maneja chat.errors; esto es lo que se escapa.
            log.error("update_task_failed", error=type(exc).__name__, exc_info=exc)

    async def drain(self, wait_seconds: float) -> int:
        """Espera a las tareas en curso; devuelve cuántas quedaron sin terminar."""
        if not self._tasks:
            return 0
        _, unfinished = await asyncio.wait(set(self._tasks), timeout=wait_seconds)
        return len(unfinished)


def build_webhook_app(
    updates: BackgroundUpdates,
    bot: Bot,
    *,
    secret: str,
    health: HealthCheck,
    drain_seconds: float = DRAIN_SECONDS,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        unfinished = await updates.drain(drain_seconds)
        log.info("webhook_stopped", unfinished_updates=unfinished)

    # Sin /docs ni /openapi.json: el servidor solo existe para Telegram y el healthcheck.
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    expected = secret.encode()

    @app.post(WEBHOOK_PATH)
    async def telegram_webhook(request: Request) -> Response:  # pyright: ignore[reportUnusedFunction]
        received = request.headers.get(SECRET_HEADER, "").encode()
        if not hmac.compare_digest(received, expected):
            log.warning("webhook_rejected", reason="bad_secret")
            return Response(status_code=401)
        try:
            update = Update.model_validate(await request.json(), context={"bot": bot})
        except (ValueError, ValidationError):
            log.warning("webhook_rejected", reason="bad_payload")
            return Response(status_code=400)
        updates.submit(update)
        return Response(status_code=200)

    @app.get("/health")
    async def health_endpoint() -> JSONResponse:  # pyright: ignore[reportUnusedFunction]
        ok = await health()
        return JSONResponse(
            {"status": "ok" if ok else "unavailable"}, status_code=200 if ok else 503
        )

    return app


class WebhookServer(uvicorn.Server):
    """uvicorn que, al recibir SIGTERM o SIGINT, termina sin volver a lanzar la señal.

    uvicorn re-lanza la señal al salir de `serve()`; con SIGTERM eso mata el proceso antes
    de que `main()` cierre el scheduler, la sesión del bot y el pool de la base de datos.
    """

    @contextmanager
    def capture_signals(self) -> Generator[None]:
        previous = {sig: signal.signal(sig, self.handle_exit) for sig in _SIGNALS}
        try:
            yield
        finally:
            for sig, handler in previous.items():
                signal.signal(sig, handler)


_SIGNALS = (signal.SIGINT, signal.SIGTERM)


def build_server(app: FastAPI, port: int) -> WebhookServer:
    config = uvicorn.Config(
        app,
        host="0.0.0.0",  # dentro del contenedor; Railway expone el puerto por su proxy
        port=port,
        log_config=None,  # los logs van por structlog y logging estándar (observability)
        access_log=False,  # cada update sería una línea; ya se registra con update_id
        proxy_headers=True,
    )
    return WebhookServer(config)
