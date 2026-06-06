from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.exceptions import HomeAssistantError

from custom_components.parkeren_nijmegen.const import DOMAIN
from custom_components.parkeren_nijmegen.exceptions import (
    ProviderError,
)


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    return


@pytest.fixture
def mock_coordinator(hass):
    coordinator = MagicMock()
    coordinator.api = MagicMock()
    coordinator.api.start_reservation = AsyncMock()
    coordinator.api.end_reservation = AsyncMock()
    coordinator.async_request_refresh = AsyncMock()
    return coordinator


@pytest.fixture
async def setup_integration(hass, mock_coordinator):
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.parkeren_nijmegen.services import async_register_services

    entry = MockConfigEntry(
        domain=DOMAIN,
        entry_id="test-entry-id",
        data={"username": "u", "password": "p"},
    )
    entry.add_to_hass(hass)
    hass.data.setdefault(DOMAIN, {})["test-entry-id"] = mock_coordinator
    async_register_services(hass)
    return entry, mock_coordinator


async def test_start_reservation_calls_api(hass, setup_integration):
    entry, coordinator = setup_integration
    end_time = (datetime.now(UTC) + timedelta(hours=1)).isoformat()

    await hass.services.async_call(
        DOMAIN,
        "start_reservation",
        {
            "config_entry_id": "test-entry-id",
            "license_plate": "AB12CD",
            "end_time": end_time,
        },
        blocking=True,
    )

    coordinator.api.start_reservation.assert_called_once()
    call_args = coordinator.api.start_reservation.call_args
    assert call_args[0][0] == "AB12CD"
    assert call_args[0][1].tzinfo is not None
    coordinator.async_request_refresh.assert_called_once()


async def test_end_reservation_calls_api(hass, setup_integration):
    entry, coordinator = setup_integration

    await hass.services.async_call(
        DOMAIN,
        "end_reservation",
        {
            "config_entry_id": "test-entry-id",
            "reservation_id": "123",
        },
        blocking=True,
    )

    coordinator.api.end_reservation.assert_called_once_with("123")
    coordinator.async_request_refresh.assert_called_once()


async def test_start_reservation_raises_on_api_error(hass, setup_integration):
    entry, coordinator = setup_integration
    coordinator.api.start_reservation = AsyncMock(side_effect=ProviderError("failed"))
    end_time = (datetime.now(UTC) + timedelta(hours=1)).isoformat()

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            "start_reservation",
            {
                "config_entry_id": "test-entry-id",
                "license_plate": "AB12CD",
                "end_time": end_time,
            },
            blocking=True,
        )


async def test_end_reservation_raises_on_api_error(hass, setup_integration):
    entry, coordinator = setup_integration
    coordinator.api.end_reservation = AsyncMock(side_effect=ProviderError("failed"))

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            "end_reservation",
            {
                "config_entry_id": "test-entry-id",
                "reservation_id": "123",
            },
            blocking=True,
        )


async def test_service_unknown_entry_raises(hass, setup_integration):
    end_time = (datetime.now(UTC) + timedelta(hours=1)).isoformat()

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            "start_reservation",
            {
                "config_entry_id": "nonexistent-id",
                "license_plate": "AB12CD",
                "end_time": end_time,
            },
            blocking=True,
        )
