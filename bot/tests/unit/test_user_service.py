import pytest

from gastos.domain.errors import InvalidPreference
from gastos.services.users import UserService
from tests.fakes import FakeUserStore


@pytest.fixture
def store() -> FakeUserStore:
    return FakeUserStore()


@pytest.fixture
def service(store: FakeUserStore) -> UserService:
    return UserService(store)


async def test_registra_al_usuario_solo_la_primera_vez(
    service: UserService, store: FakeUserStore
) -> None:
    first = await service.identify(42, "Ana")
    again = await service.identify(42, "Ana")
    assert first.id == again.id
    assert store.created == 1
    assert not first.is_onboarded


async def test_onboarding_completo(service: UserService) -> None:
    user = await service.identify(42, "Ana")
    user = await service.choose_currency(user, "COP")
    user = await service.choose_ves_rate_source(user, "bcv")
    user = await service.finish_onboarding(user, "America/Bogota")
    assert (user.default_currency, user.ves_rate_source, user.timezone) == (
        "COP",
        "bcv",
        "America/Bogota",
    )
    assert user.is_onboarded


async def test_rechaza_valores_manipulados_sin_tocar_la_bd(
    service: UserService, store: FakeUserStore
) -> None:
    user = await service.identify(42, "Ana")
    with pytest.raises(InvalidPreference):
        await service.choose_currency(user, "EUR")
    with pytest.raises(InvalidPreference):
        await service.finish_onboarding(user, "Mars/Olympus")
    assert store.by_id[user.id] == user
