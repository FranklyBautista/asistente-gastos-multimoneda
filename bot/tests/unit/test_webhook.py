import asyncio
from typing import Any

import pytest
from aiogram import Bot
from aiogram.types import Update
from fastapi.testclient import TestClient

from gastos.chat.webhook import (
    SECRET_HEADER,
    WEBHOOK_PATH,
    BackgroundUpdates,
    build_webhook_app,
)

SECRET = "x" * 24  # valor de prueba evidente
UPDATE = {
    "update_id": 10,
    "message": {
        "message_id": 1,
        "date": 1_700_000_000,
        "chat": {"id": 7, "type": "private"},
        "from": {"id": 7, "is_bot": False, "first_name": "Ana"},
        "text": "gasté 15 bs en pan",
    },
}


class FakeDispatcher:
    def __init__(self, *, delay: float = 0, fail: bool = False) -> None:
        self.updates: list[Update] = []
        self._delay = delay
        self._fail = fail

    async def feed_update(self, bot: Bot, update: Update, **kwargs: Any) -> Any:
        await asyncio.sleep(self._delay)
        if self._fail:
            raise RuntimeError("se escapó del manejador de errores")
        self.updates.append(update)


def make_bot() -> Bot:
    return Bot("123456:" + "A" * 35)  # formato válido; nunca se conecta en estas pruebas


def make_client(dp: FakeDispatcher, *, healthy: bool = True) -> TestClient:
    bot = make_bot()

    async def health() -> bool:
        return healthy

    app = build_webhook_app(BackgroundUpdates(bot, dp), bot, secret=SECRET, health=health)
    return TestClient(app)


def test_procesa_el_update_con_el_secreto_correcto() -> None:
    dp = FakeDispatcher()
    with make_client(dp) as client:
        response = client.post(WEBHOOK_PATH, json=UPDATE, headers={SECRET_HEADER: SECRET})
    # Al salir del `with` se ejecuta el apagado, que espera a las tareas pendientes.
    assert response.status_code == 200
    assert [u.update_id for u in dp.updates] == [10]
    assert dp.updates[0].message is not None
    assert dp.updates[0].message.text == "gasté 15 bs en pan"


@pytest.mark.parametrize("headers", [{}, {SECRET_HEADER: "otro-secreto-cualquiera"}])
def test_rechaza_sin_el_secreto(headers: dict[str, str]) -> None:
    dp = FakeDispatcher()
    with make_client(dp) as client:
        response = client.post(WEBHOOK_PATH, json=UPDATE, headers=headers)
    assert response.status_code == 401
    assert dp.updates == []


def test_rechaza_un_cuerpo_que_no_es_un_update() -> None:
    dp = FakeDispatcher()
    with make_client(dp) as client:
        bad_json = client.post(
            WEBHOOK_PATH,
            content=b"no es json",
            headers={SECRET_HEADER: SECRET, "content-type": "application/json"},
        )
        bad_update = client.post(
            WEBHOOK_PATH, json={"sin": "update_id"}, headers={SECRET_HEADER: SECRET}
        )
    assert bad_json.status_code == 400
    assert bad_update.status_code == 400
    assert dp.updates == []


def test_un_fallo_en_segundo_plano_no_afecta_la_respuesta() -> None:
    with make_client(FakeDispatcher(fail=True)) as client:
        response = client.post(WEBHOOK_PATH, json=UPDATE, headers={SECRET_HEADER: SECRET})
    assert response.status_code == 200


@pytest.mark.parametrize(
    ("healthy", "status", "body"), [(True, 200, "ok"), (False, 503, "unavailable")]
)
def test_health_refleja_la_base_de_datos(healthy: bool, status: int, body: str) -> None:
    with make_client(FakeDispatcher(), healthy=healthy) as client:
        response = client.get("/health")
    assert response.status_code == status
    assert response.json() == {"status": body}


def test_no_expone_la_documentacion_de_la_api() -> None:
    with make_client(FakeDispatcher()) as client:
        assert client.get("/docs").status_code == 404
        assert client.get("/openapi.json").status_code == 404


async def test_drain_espera_a_las_tareas_en_curso() -> None:
    dp = FakeDispatcher(delay=0.05)
    updates = BackgroundUpdates(make_bot(), dp)
    updates.submit(Update.model_validate(UPDATE))
    assert updates.pending == 1
    assert await updates.drain(wait_seconds=2) == 0
    assert len(dp.updates) == 1
    assert updates.pending == 0


async def test_drain_respeta_el_limite_de_tiempo() -> None:
    updates = BackgroundUpdates(make_bot(), FakeDispatcher(delay=5))
    updates.submit(Update.model_validate(UPDATE))
    assert await updates.drain(wait_seconds=0.01) == 1
