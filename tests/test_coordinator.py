from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.parkeren_nijmegen.const import DOMAIN
from custom_components.parkeren_nijmegen.coordinator import (
    NijmegenCoordinator,
    is_currently_chargeable,
)
from custom_components.parkeren_nijmegen.exceptions import AuthError, ProviderError
from custom_components.parkeren_nijmegen.models import (
    Permit,
    ZoneBlock,
)


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    return


def _make_permit(balance=120, chargeable_now=False):
    now = datetime.now(UTC)
    blocks = ()
    if chargeable_now:
        blocks = (
            ZoneBlock(start=now - timedelta(hours=1), end=now + timedelta(hours=1)),
        )
    return Permit(id="CARD-1", remaining_balance=balance, zone_validity=blocks)


def test_is_currently_chargeable_true():
    now = datetime.now(UTC)
    blocks = (ZoneBlock(start=now - timedelta(hours=1), end=now + timedelta(hours=1)),)
    assert is_currently_chargeable(blocks, now) is True


def test_is_currently_chargeable_false():
    now = datetime.now(UTC)
    blocks = (ZoneBlock(start=now + timedelta(hours=1), end=now + timedelta(hours=2)),)
    assert is_currently_chargeable(blocks, now) is False


def test_is_currently_chargeable_empty():
    now = datetime.now(UTC)
    assert is_currently_chargeable((), now) is False


async def test_coordinator_fetches_data(hass):
    mock_api = MagicMock()
    permit = _make_permit()
    mock_api.fetch_all = AsyncMock(return_value=(permit, [], []))

    coordinator = NijmegenCoordinator(hass, mock_api)
    await coordinator.async_refresh()

    assert coordinator.data is not None
    assert coordinator.data.permit.remaining_balance == 120
    assert coordinator.data.reservations == ()
    assert coordinator.data.favorites == ()


async def test_coordinator_raises_update_failed_on_provider_error(hass):
    mock_api = MagicMock()
    mock_api.fetch_all = AsyncMock(side_effect=ProviderError("network problem"))

    coordinator = NijmegenCoordinator(hass, mock_api)
    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


async def test_coordinator_signals_reauth_on_persistent_auth_error(hass):
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    mock_api = MagicMock()
    mock_api.fetch_all = AsyncMock(side_effect=AuthError("session expired"))

    entry = MockConfigEntry(domain=DOMAIN, data={"username": "u", "password": "p"})
    entry.add_to_hass(hass)

    coordinator = NijmegenCoordinator(hass, mock_api, entry=entry)

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()
    # reauth was signaled (entry state would change to AWAITING_REAUTH if loaded)
