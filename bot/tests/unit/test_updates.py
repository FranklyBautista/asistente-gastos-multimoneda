"""Idempotencia de updates: un update repetido no llega a los handlers (ADR 0011)."""

from datetime import UTC, datetime
from typing import Any

from aiogram.types import TelegramObject, Update

from gastos.chat.middlewares import DeduplicateMiddleware
from gastos.services.updates import RETENTION, UpdateLedger
from tests.fakes import FakeUpdateStore


class FakeBot:
    def __init__(self, bot_id: int) -> None:
        self.id = bot_id


class Recorder:
    def __init__(self) -> None:
        self.calls = 0

    async def __call__(self, event: TelegramObject, data: dict[str, Any]) -> str:
        self.calls += 1
        return "ok"


async def test_un_update_repetido_se_descarta() -> None:
    handler = Recorder()
    middleware = DeduplicateMiddleware(UpdateLedger(FakeUpdateStore()))
    data = {"bot": FakeBot(1)}
    assert await middleware(handler, Update(update_id=10), data) == "ok"
    assert await middleware(handler, Update(update_id=10), data) is None
    assert await middleware(handler, Update(update_id=11), data) == "ok"
    assert handler.calls == 2


async def test_el_update_id_es_por_bot() -> None:
    handler = Recorder()
    middleware = DeduplicateMiddleware(UpdateLedger(FakeUpdateStore()))
    await middleware(handler, Update(update_id=10), {"bot": FakeBot(1)})
    await middleware(handler, Update(update_id=10), {"bot": FakeBot(2)})
    assert handler.calls == 2


async def test_purga_lo_anterior_a_la_retencion() -> None:
    store = FakeUpdateStore()
    now = datetime(2026, 11, 5, 8, tzinfo=UTC)
    await UpdateLedger(store, clock=lambda: now).purge()
    assert store.cutoffs == [now - RETENTION]
