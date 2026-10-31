from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from gastos.domain.conversion import Rate
from gastos.domain.errors import RateUnavailable
from gastos.rates.base import RateFetchError
from gastos.services.rates import BOARD, RateService
from tests.fakes import FakeRateSources, FakeRateStore, make_user

NOW = datetime(2026, 10, 27, 12, tzinfo=UTC)
MAX_AGE = timedelta(hours=6)

BCV = Rate("VES", "bcv", Decimal("0.001127"), NOW)
PARALLEL = Rate("VES", "parallel", Decimal("0.000998"), NOW)
P2P = Rate("VES", "p2p", Decimal("0.000993"), NOW)
COP = Rate("COP", "fx", Decimal("0.000318"), NOW)
USDT = Rate("USDT", "coingecko", Decimal("0.9988"), NOW)


def sources(*down: str, error: Exception | None = None) -> FakeRateSources:
    """Fuentes simuladas; las nombradas en `down` fallan con `error`."""
    fail = error or RateFetchError("fuente caída")
    return FakeRateSources(
        dolarapi=fail if "dolarapi" in down else [BCV, PARALLEL],
        p2p=fail if "p2p" in down else P2P,
        cop=fail if "cop" in down else COP,
        usdt=fail if "usdt" in down else USDT,
    )


def service(store: FakeRateStore, srcs: FakeRateSources | None = None) -> RateService:
    return RateService(store, srcs or sources(), MAX_AGE, clock=lambda: NOW)


async def test_refresco_guarda_las_cinco_tasas() -> None:
    store = FakeRateStore()
    srcs = sources()
    saved = await service(store, srcs).refresh()
    assert {(r.currency, r.source) for r in saved} == set(BOARD)
    assert store.rows == saved
    assert srcs.p2p_crossed_with == USDT


@pytest.mark.parametrize("error", [RateFetchError("caída"), ValueError("bug del cliente")])
async def test_una_fuente_caida_no_frena_a_las_demas(error: Exception) -> None:
    store = FakeRateStore()
    saved = await service(store, sources("cop", error=error)).refresh()
    assert [r.source for r in saved] == ["bcv", "parallel", "coingecko", "p2p"]


async def test_si_coingecko_cae_el_p2p_usa_el_ultimo_usdt_guardado() -> None:
    old_usdt = Rate("USDT", "coingecko", Decimal("0.997"), NOW - timedelta(hours=3))
    srcs = sources("usdt")
    saved = await service(FakeRateStore(old_usdt), srcs).refresh()
    assert srcs.p2p_crossed_with == old_usdt
    assert P2P in saved


async def test_sin_ningun_usdt_no_se_calcula_el_p2p() -> None:
    srcs = sources("usdt")
    saved = await service(FakeRateStore(), srcs).refresh()
    assert srcs.p2p_crossed_with is None
    assert [r.source for r in saved] == ["bcv", "parallel", "fx"]


async def test_si_todo_cae_no_se_guarda_nada() -> None:
    store = FakeRateStore()
    assert await service(store, sources("dolarapi", "cop", "usdt")).refresh() == []
    assert store.rows == []


async def test_lee_la_tasa_mas_reciente() -> None:
    older = Rate("VES", "bcv", Decimal("0.0012"), NOW - timedelta(hours=1))
    current = await service(FakeRateStore(older, BCV)).current("VES", "bcv")
    assert current.rate == BCV
    assert not current.stale


async def test_fuente_caida_usa_la_ultima_tasa_marcada_como_vieja() -> None:
    old = Rate("VES", "bcv", Decimal("0.0012"), NOW - timedelta(hours=7))
    current = await service(FakeRateStore(old)).current("VES", "bcv")
    assert current.rate == old
    assert current.stale


async def test_sin_ninguna_tasa_guardada_no_se_inventa_una() -> None:
    with pytest.raises(RateUnavailable):
        await service(FakeRateStore(BCV)).current("VES", "p2p")


async def test_la_tasa_del_bolivar_sale_de_la_preferencia_del_usuario() -> None:
    rates = service(FakeRateStore(BCV, PARALLEL, P2P, COP))
    user = make_user()  # ves_rate_source = "parallel"
    assert (await rates.for_user(user, "VES")).rate == PARALLEL
    assert (await rates.for_user(user, "COP")).rate == COP


async def test_tablero_con_las_tasas_que_faltan_en_none() -> None:
    board = await service(FakeRateStore(BCV, COP)).board()
    assert [(currency, source) for currency, source, _ in board] == list(BOARD)
    assert [current.rate if current else None for _, _, current in board] == [
        BCV,
        None,
        None,
        COP,
        None,
    ]
