from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr

from custom_components.parkeren_nijmegen.const import DOMAIN
from custom_components.parkeren_nijmegen.exceptions import (
    ProviderError,
)
from custom_components.parkeren_nijmegen.models import Reservation


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
    coordinator.data = None
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

    dev_reg = dr.async_get(hass)
    device = dev_reg.async_get_or_create(
        config_entry_id="test-entry-id",
        identifiers={(DOMAIN, "test-entry-id")},
    )

    hass.data.setdefault(DOMAIN, {})["test-entry-id"] = mock_coordinator
    async_register_services(hass)
    return entry, mock_coordinator, device.id


async def test_start_reservation_calls_api(hass, setup_integration):
    entry, coordinator, device_id = setup_integration
    end_time = (datetime.now(UTC) + timedelta(hours=1)).isoformat()

    await hass.services.async_call(
        DOMAIN,
        "start_reservation",
        {
            "device_id": device_id,
            "license_plate": "AB12CD",
            "end_time": end_time,
        },
        blocking=True,
    )

    coordinator.api.start_reservation.assert_called_once()
    call_args = coordinator.api.start_reservation.call_args
    assert call_args[0][0] == "AB12CD"
    assert call_args[0][1].tzinfo is not None
    assert call_args.kwargs.get("start_time") is None
    coordinator.async_request_refresh.assert_called_once()


async def test_start_reservation_with_start_time(hass, setup_integration):
    entry, coordinator, device_id = setup_integration
    start_time = (datetime.now(UTC) + timedelta(minutes=30)).isoformat()
    end_time = (datetime.now(UTC) + timedelta(hours=2)).isoformat()

    await hass.services.async_call(
        DOMAIN,
        "start_reservation",
        {
            "device_id": device_id,
            "license_plate": "AB12CD",
            "start_time": start_time,
            "end_time": end_time,
        },
        blocking=True,
    )

    coordinator.api.start_reservation.assert_called_once()
    call_args = coordinator.api.start_reservation.call_args
    assert call_args.kwargs["start_time"] is not None
    assert call_args.kwargs["start_time"].tzinfo is not None


async def test_end_reservation_calls_api(hass, setup_integration):
    entry, coordinator, device_id = setup_integration

    await hass.services.async_call(
        DOMAIN,
        "end_reservation",
        {
            "device_id": device_id,
            "reservation_id": "123",
        },
        blocking=True,
    )

    coordinator.api.end_reservation.assert_called_once_with("123")
    coordinator.async_request_refresh.assert_called_once()


async def test_start_reservation_raises_on_api_error(hass, setup_integration):
    entry, coordinator, device_id = setup_integration
    coordinator.api.start_reservation = AsyncMock(side_effect=ProviderError("failed"))
    end_time = (datetime.now(UTC) + timedelta(hours=1)).isoformat()

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            "start_reservation",
            {
                "device_id": device_id,
                "license_plate": "AB12CD",
                "end_time": end_time,
            },
            blocking=True,
        )


async def test_end_reservation_raises_on_api_error(hass, setup_integration):
    entry, coordinator, device_id = setup_integration
    coordinator.api.end_reservation = AsyncMock(side_effect=ProviderError("failed"))

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            "end_reservation",
            {
                "device_id": device_id,
                "reservation_id": "123",
            },
            blocking=True,
        )


async def test_service_unknown_device_raises(hass, setup_integration):
    end_time = (datetime.now(UTC) + timedelta(hours=1)).isoformat()

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            "start_reservation",
            {
                "device_id": "nonexistent-device-id",
                "license_plate": "AB12CD",
                "end_time": end_time,
            },
            blocking=True,
        )


async def test_list_reservations_empty(hass, setup_integration):
    entry, coordinator, device_id = setup_integration
    coordinator.data = None

    result = await hass.services.async_call(
        DOMAIN,
        "list_reservations",
        {"device_id": device_id},
        blocking=True,
        return_response=True,
    )

    assert result == {"reservations": []}


async def test_list_reservations_with_data(hass, setup_integration):
    entry, coordinator, device_id = setup_integration
    now = datetime.now(UTC)
    active_res = Reservation(
        id="r1",
        license_plate="AB12CD",
        start_time=now - timedelta(minutes=30),
        end_time=now + timedelta(minutes=30),
    )
    future_res = Reservation(
        id="r2",
        license_plate="XY99ZZ",
        start_time=now + timedelta(hours=2),
        end_time=now + timedelta(hours=4),
    )
    coordinator.data = MagicMock()
    coordinator.data.reservations = (active_res, future_res)

    result = await hass.services.async_call(
        DOMAIN,
        "list_reservations",
        {"device_id": device_id},
        blocking=True,
        return_response=True,
    )

    assert len(result["reservations"]) == 2
    assert result["reservations"][0]["id"] == "r1"
    assert result["reservations"][0]["is_active"] is True
    assert result["reservations"][1]["id"] == "r2"
    assert result["reservations"][1]["is_active"] is False
