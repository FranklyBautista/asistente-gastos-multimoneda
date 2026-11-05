"""Vinculación con la web: códigos, servicio y texto de /vincular (ADR 0012)."""

import re
from datetime import UTC, datetime

import pytest

from gastos.chat.handlers.linking import link_text
from gastos.domain.linking import ALPHABET, CODE_LENGTH, LINK_TTL, new_code
from gastos.services.linking import AlreadyLinked, LinkCode, LinkService
from tests.fakes import FakeLinkStore, make_user

NOW = datetime(2026, 11, 6, 12, tzinfo=UTC)
# El mismo patrón que el check de link_codes.code en la migración.
DB_PATTERN = re.compile(r"^[A-HJ-NP-Z2-9]{8}$")


def test_el_codigo_cumple_el_formato_de_la_base_de_datos() -> None:
    for _ in range(200):
        assert DB_PATTERN.fullmatch(new_code())


def test_el_alfabeto_evita_caracteres_confusos() -> None:
    assert not set("IO01") & set(ALPHABET)
    assert len(set(ALPHABET)) == 32
    assert CODE_LENGTH == 8


async def test_emite_un_codigo_que_vence_en_10_minutos() -> None:
    store = FakeLinkStore()
    user = make_user(onboarded=True)
    result = await LinkService(store, clock=lambda: NOW, generate=lambda: "ABCD2345").issue(user)
    assert result == LinkCode("ABCD2345", NOW + LINK_TTL)
    assert store.issued == [(user.id, "ABCD2345", NOW + LINK_TTL)]


async def test_si_ya_esta_vinculado_no_emite_codigo() -> None:
    store = FakeLinkStore(linked=True)
    result = await LinkService(store, clock=lambda: NOW).issue(make_user(onboarded=True))
    assert isinstance(result, AlreadyLinked)
    assert store.issued == []


async def test_reintenta_si_el_codigo_ya_existe() -> None:
    codes = iter(["TAKEN234", "FRESH234"])
    store = FakeLinkStore(taken={"TAKEN234"})
    result = await LinkService(store, clock=lambda: NOW, generate=lambda: next(codes)).issue(
        make_user(onboarded=True)
    )
    assert isinstance(result, LinkCode)
    assert result.code == "FRESH234"


async def test_falla_si_todos_los_intentos_chocan() -> None:
    store = FakeLinkStore(taken={"TAKEN234"})
    service = LinkService(store, clock=lambda: NOW, generate=lambda: "TAKEN234")
    with pytest.raises(RuntimeError):
        await service.issue(make_user(onboarded=True))


def test_el_mensaje_incluye_codigo_enlace_y_vencimiento() -> None:
    text = link_text("ABCD2345", "https://gastos.example.com")
    assert "ABCD2345" in text
    assert "https://gastos.example.com/vincular" in text
    assert "10 minutos" in text


def test_sin_url_de_la_web_el_mensaje_igual_sirve() -> None:
    text = link_text("ABCD2345", None)
    assert "ABCD2345" in text
    assert "http" not in text
