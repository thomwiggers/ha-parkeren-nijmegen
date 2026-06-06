from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr

from custom_components.parkeren_nijmegen.const import DOMAIN
from custom_components.parkeren_nijmegen.exceptions import ProviderError
from custom_components.parkeren_nijmegen.models import (
    CoordinatorData,
    Favorite,
    Permit,
    Reservation,
    ZoneBlock,
)


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    return


def _make_permit(balance: int = 600) -> Permit:
    now = datetime.now(UTC)
    block = ZoneBlock(
        start=now + timedelta(hours=1),
        end=now + timedelta(hours=3),
    )
    return Permit(id="TESTPERMIT", remaining_balance=balance, zone_validity=(block,))


@pytest.fixture
def mock_coordinator(hass):
    coordinator = MagicMock()
    coordinator.api = MagicMock()
    coordinator.api.start_reservation = AsyncMock()
    coordinator.api.end_reservation = AsyncMock()
    coordinator.api.add_favorite = AsyncMock()
    coordinator.api.remove_favorite = AsyncMock()
    coordinator.async_request_refresh = AsyncMock()
    coordinator.async_refresh = AsyncMock()
    coordinator.last_update_success = True
    coordinator.data = None
    coordinator._entry = None
    return coordinator


@pytest.fixture
async def setup_integration(hass, mock_coordinator):
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.parkeren_nijmegen.services import async_register_services

    entry = MockConfigEntry(
        domain=DOMAIN,
        entry_id="test-entry-id",
        title="Parkeren Test",
        data={"username": "u", "password": "p"},
    )
    entry.add_to_hass(hass)
    mock_coordinator._entry = entry

    dev_reg = dr.async_get(hass)
    device = dev_reg.async_get_or_create(
        config_entry_id="test-entry-id",
        identifiers={(DOMAIN, "test-entry-id")},
    )

    hass.data.setdefault(DOMAIN, {})["test-entry-id"] = mock_coordinator
    async_register_services(hass)
    return entry, mock_coordinator, device.id


# ── start_reservation ─────────────────────────────────────────────────────────


async def test_start_reservation_calls_api(hass, setup_integration):
    entry, coordinator, device_id = setup_integration
    end_time = (datetime.now(UTC) + timedelta(hours=1)).isoformat()

    await hass.services.async_call(
        DOMAIN,
        "start_reservation",
        {"device_id": device_id, "license_plate": "AB12CD", "end_time": end_time},
        blocking=True,
    )

    coordinator.api.start_reservation.assert_called_once()
    call_args = coordinator.api.start_reservation.call_args
    assert call_args[0][0] == "AB12CD"
    assert call_args[0][1].tzinfo is not None
    assert call_args.kwargs["start_time"] is not None
    coordinator.async_request_refresh.assert_called_once()


async def test_start_reservation_with_explicit_start_time(hass, setup_integration):
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

    call_args = coordinator.api.start_reservation.call_args
    assert call_args.kwargs["start_time"].tzinfo is not None


async def test_start_reservation_clamps_past_start_time(hass, setup_integration):
    entry, coordinator, device_id = setup_integration
    past_start = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    end_time = (datetime.now(UTC) + timedelta(hours=2)).isoformat()

    await hass.services.async_call(
        DOMAIN,
        "start_reservation",
        {
            "device_id": device_id,
            "license_plate": "AB12CD",
            "start_time": past_start,
            "end_time": end_time,
        },
        blocking=True,
    )

    # start_time must have been clamped to ~now+1min
    call_args = coordinator.api.start_reservation.call_args
    assert call_args.kwargs["start_time"] >= datetime.now(UTC)


async def test_start_reservation_end_before_start_raises(hass, setup_integration):
    entry, coordinator, device_id = setup_integration
    start_time = (datetime.now(UTC) + timedelta(hours=2)).isoformat()
    end_time = (datetime.now(UTC) + timedelta(hours=1)).isoformat()

    with pytest.raises(HomeAssistantError, match="end_time must be after start_time"):
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


async def test_start_reservation_raises_on_api_error(hass, setup_integration):
    entry, coordinator, device_id = setup_integration
    coordinator.api.start_reservation = AsyncMock(side_effect=ProviderError("failed"))

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            "start_reservation",
            {
                "device_id": device_id,
                "license_plate": "AB12CD",
                "end_time": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
            },
            blocking=True,
        )


# ── update_reservation ────────────────────────────────────────────────────────


async def test_update_reservation_uses_coordinator_data_defaults(
    hass, setup_integration
):
    entry, coordinator, device_id = setup_integration
    now = datetime.now(UTC)
    existing = Reservation(
        id="r1",
        license_plate="AB12CD",
        start_time=now - timedelta(minutes=5),
        end_time=now + timedelta(hours=1),
    )
    coordinator.data = CoordinatorData(
        permit=_make_permit(),
        reservations=(existing,),
        favorites=(),
    )
    new_end = (now + timedelta(hours=2)).isoformat()

    await hass.services.async_call(
        DOMAIN,
        "update_reservation",
        {"device_id": device_id, "reservation_id": "r1", "end_time": new_end},
        blocking=True,
    )

    coordinator.api.end_reservation.assert_called_once_with("r1")
    coordinator.api.start_reservation.assert_called_once()
    call_args = coordinator.api.start_reservation.call_args
    assert call_args[0][0] == "AB12CD"  # plate from existing reservation


async def test_update_reservation_no_fields_raises(hass, setup_integration):
    entry, coordinator, device_id = setup_integration

    with pytest.raises(HomeAssistantError, match="at least one"):
        await hass.services.async_call(
            DOMAIN,
            "update_reservation",
            {"device_id": device_id, "reservation_id": "r1"},
            blocking=True,
        )


async def test_update_reservation_missing_fields_without_data_raises(
    hass, setup_integration
):
    entry, coordinator, device_id = setup_integration
    coordinator.data = None

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            "update_reservation",
            {
                "device_id": device_id,
                "reservation_id": "r1",
                "end_time": (datetime.now(UTC) + timedelta(hours=2)).isoformat(),
            },
            blocking=True,
        )


# ── end_reservation ───────────────────────────────────────────────────────────


async def test_end_reservation_calls_api(hass, setup_integration):
    entry, coordinator, device_id = setup_integration

    await hass.services.async_call(
        DOMAIN,
        "end_reservation",
        {"device_id": device_id, "reservation_id": "123"},
        blocking=True,
    )

    coordinator.api.end_reservation.assert_called_once_with("123")
    coordinator.async_request_refresh.assert_called_once()


async def test_end_reservation_raises_on_api_error(hass, setup_integration):
    entry, coordinator, device_id = setup_integration
    coordinator.api.end_reservation = AsyncMock(side_effect=ProviderError("failed"))

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            "end_reservation",
            {"device_id": device_id, "reservation_id": "123"},
            blocking=True,
        )


# ── list_reservations ─────────────────────────────────────────────────────────


async def test_list_reservations_empty(hass, setup_integration):
    entry, coordinator, device_id = setup_integration
    coordinator.async_refresh = AsyncMock()
    coordinator.data = CoordinatorData(
        permit=_make_permit(), reservations=(), favorites=()
    )

    result = await hass.services.async_call(
        DOMAIN,
        "list_reservations",
        {"device_id": device_id},
        blocking=True,
        return_response=True,
    )

    assert result["count"] == 0
    assert result["active_count"] == 0
    assert result["future_count"] == 0
    assert result["reservations"] == []
    assert result["stale"] is False


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
    expired_res = Reservation(
        id="r3",
        license_plate="ZZ00ZZ",
        start_time=now - timedelta(hours=2),
        end_time=now - timedelta(hours=1),
    )
    fav = Favorite(license_plate="AB12CD", name="Bezoeker Jan")
    coordinator.data = CoordinatorData(
        permit=_make_permit(),
        reservations=(active_res, future_res, expired_res),
        favorites=(fav,),
    )
    coordinator.async_refresh = AsyncMock()

    result = await hass.services.async_call(
        DOMAIN,
        "list_reservations",
        {"device_id": device_id},
        blocking=True,
        return_response=True,
    )

    assert result["count"] == 2  # expired excluded
    assert result["active_count"] == 1
    assert result["future_count"] == 1
    r1 = next(r for r in result["reservations"] if r["id"] == "r1")
    assert r1["is_active"] is True
    assert r1["favorite_name"] == "Bezoeker Jan"
    r2 = next(r for r in result["reservations"] if r["id"] == "r2")
    assert r2["is_active"] is False
    assert r2["favorite_name"] is None


async def test_list_reservations_stale_on_refresh_failure(hass, setup_integration):
    entry, coordinator, device_id = setup_integration
    coordinator.data = CoordinatorData(
        permit=_make_permit(), reservations=(), favorites=()
    )
    coordinator.async_refresh = AsyncMock(side_effect=Exception("network error"))

    result = await hass.services.async_call(
        DOMAIN,
        "list_reservations",
        {"device_id": device_id},
        blocking=True,
        return_response=True,
    )

    assert result["stale"] is True


# ── favorites ─────────────────────────────────────────────────────────────────


async def test_add_favorite_calls_api(hass, setup_integration):
    entry, coordinator, device_id = setup_integration

    await hass.services.async_call(
        DOMAIN,
        "add_favorite",
        {"device_id": device_id, "license_plate": "AB12CD", "name": "Jan"},
        blocking=True,
    )

    coordinator.api.add_favorite.assert_called_once_with("AB12CD", "Jan")
    coordinator.async_request_refresh.assert_called_once()


async def test_add_favorite_without_name(hass, setup_integration):
    entry, coordinator, device_id = setup_integration

    await hass.services.async_call(
        DOMAIN,
        "add_favorite",
        {"device_id": device_id, "license_plate": "AB12CD"},
        blocking=True,
    )

    coordinator.api.add_favorite.assert_called_once_with("AB12CD", None)


async def test_update_favorite_calls_api(hass, setup_integration):
    entry, coordinator, device_id = setup_integration

    await hass.services.async_call(
        DOMAIN,
        "update_favorite",
        {"device_id": device_id, "license_plate": "AB12CD", "name": "Nieuwe naam"},
        blocking=True,
    )

    coordinator.api.add_favorite.assert_called_once_with("AB12CD", "Nieuwe naam")


async def test_remove_favorite_calls_api(hass, setup_integration):
    entry, coordinator, device_id = setup_integration

    await hass.services.async_call(
        DOMAIN,
        "remove_favorite",
        {"device_id": device_id, "license_plate": "AB12CD"},
        blocking=True,
    )

    coordinator.api.remove_favorite.assert_called_once_with("AB12CD")
    coordinator.async_request_refresh.assert_called_once()


async def test_list_favorites_returns_data(hass, setup_integration):
    entry, coordinator, device_id = setup_integration
    coordinator.async_refresh = AsyncMock()
    coordinator.data = CoordinatorData(
        permit=_make_permit(),
        reservations=(),
        favorites=(
            Favorite(license_plate="AB12CD", name="Jan"),
            Favorite(license_plate="XY99ZZ", name="Piet"),
        ),
    )

    result = await hass.services.async_call(
        DOMAIN,
        "list_favorites",
        {"device_id": device_id},
        blocking=True,
        return_response=True,
    )

    assert result["count"] == 2
    assert {"license_plate": "AB12CD", "name": "Jan"} in result["favorites"]
    assert result["stale"] is False


async def test_favorite_raises_on_api_error(hass, setup_integration):
    entry, coordinator, device_id = setup_integration
    coordinator.api.add_favorite = AsyncMock(side_effect=ProviderError("nope"))

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            "add_favorite",
            {"device_id": device_id, "license_plate": "AB12CD"},
            blocking=True,
        )


# ── get_status ────────────────────────────────────────────────────────────────


async def test_get_status_returns_permit_data(hass, setup_integration):
    entry, coordinator, device_id = setup_integration
    coordinator.async_refresh = AsyncMock()
    coordinator.data = CoordinatorData(
        permit=_make_permit(balance=300),
        reservations=(),
        favorites=(),
    )

    result = await hass.services.async_call(
        DOMAIN,
        "get_status",
        {"device_id": device_id},
        blocking=True,
        return_response=True,
    )

    assert result["permit_id"] == "TESTPERMIT"
    assert result["remaining_balance_minutes"] == 300
    assert result["remaining_balance_hours"] == pytest.approx(5.0)
    assert "is_chargeable_now" in result
    assert "next_window_start" in result
    assert result["stale"] is False


# ── get_entry_info ────────────────────────────────────────────────────────────


async def test_get_entry_info_returns_metadata(hass, setup_integration):
    entry, coordinator, device_id = setup_integration
    coordinator.data = CoordinatorData(
        permit=_make_permit(), reservations=(), favorites=()
    )

    result = await hass.services.async_call(
        DOMAIN,
        "get_entry_info",
        {"device_id": device_id},
        blocking=True,
        return_response=True,
    )

    assert result["permit_id"] == "TESTPERMIT"
    assert result["title"] == "Parkeren Test"


# ── device resolution ─────────────────────────────────────────────────────────


async def test_service_unknown_device_raises(hass, setup_integration):
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            "start_reservation",
            {
                "device_id": "nonexistent-device-id",
                "license_plate": "AB12CD",
                "end_time": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
            },
            blocking=True,
        )
