from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN
from .coordinator import (
    NijmegenCoordinator,
    current_or_next_window,
    is_currently_chargeable,
)
from .exceptions import NijmegenParkingError
from .models import CoordinatorData

_TZ = ZoneInfo("Europe/Amsterdam")

_LOGGER = logging.getLogger(__name__)

_START_RESERVATION_SCHEMA = vol.Schema(
    {
        vol.Required("device_id"): str,
        vol.Required("license_plate"): str,
        vol.Required("end_time"): str,
        vol.Optional("start_time"): str,
    }
)

_UPDATE_RESERVATION_SCHEMA = vol.Schema(
    {
        vol.Required("device_id"): str,
        vol.Required("reservation_id"): str,
        vol.Optional("license_plate"): str,
        vol.Optional("start_time"): str,
        vol.Optional("end_time"): str,
    }
)

_END_RESERVATION_SCHEMA = vol.Schema(
    {
        vol.Required("device_id"): str,
        vol.Required("reservation_id"): str,
    }
)

_ADD_FAVORITE_SCHEMA = vol.Schema(
    {
        vol.Required("device_id"): str,
        vol.Required("license_plate"): str,
        vol.Optional("name"): str,
    }
)

_UPDATE_FAVORITE_SCHEMA = vol.Schema(
    {
        vol.Required("device_id"): str,
        vol.Required("license_plate"): str,
        vol.Optional("name"): str,
    }
)

_REMOVE_FAVORITE_SCHEMA = vol.Schema(
    {
        vol.Required("device_id"): str,
        vol.Required("license_plate"): str,
    }
)

_DEVICE_SCHEMA = vol.Schema({vol.Required("device_id"): str})


def _get_coordinator(hass: HomeAssistant, entry_id: str) -> NijmegenCoordinator:
    coordinator = hass.data.get(DOMAIN, {}).get(entry_id)
    if coordinator is None:
        raise HomeAssistantError(f"No Parkeren Nijmegen entry found: {entry_id}")
    return coordinator


def _get_coordinator_by_device(
    hass: HomeAssistant, device_id: str
) -> NijmegenCoordinator:
    dev_reg = dr.async_get(hass)
    device = dev_reg.async_get(device_id)
    if device is None:
        raise HomeAssistantError(f"Device not found: {device_id}")
    entry_id = next(
        (ident[1] for ident in device.identifiers if ident[0] == DOMAIN), None
    )
    if entry_id is None:
        raise HomeAssistantError(
            f"Device {device_id} is not a Parkeren Nijmegen device"
        )
    return _get_coordinator(hass, entry_id)


def _parse_time(value: str) -> datetime:
    try:
        dt = datetime.fromisoformat(value)
    except ValueError as err:
        raise HomeAssistantError(f"Invalid datetime: {err}") from err
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_TZ)
    return dt


async def _refresh_data(
    coordinator: NijmegenCoordinator,
) -> tuple[CoordinatorData, bool]:
    """Force-refresh coordinator and return (data, stale).

    stale=True when refresh fails but cached data is available.
    """
    stale = False
    try:
        await coordinator.async_refresh()
    except Exception:
        if coordinator.data is not None:
            stale = True
        else:
            raise HomeAssistantError("Failed to fetch current data from provider")
    if not stale and not coordinator.last_update_success:
        if coordinator.data is not None:
            stale = True
        else:
            raise HomeAssistantError("Failed to fetch current data from provider")
    if coordinator.data is None:
        raise HomeAssistantError("No data available")
    return coordinator.data, stale


def async_register_services(hass: HomeAssistant) -> None:
    async def handle_start_reservation(call: ServiceCall) -> None:
        coordinator = _get_coordinator_by_device(hass, call.data["device_id"])
        end_time = _parse_time(call.data["end_time"])
        now = datetime.now(UTC)
        min_start = now + timedelta(minutes=1)
        if "start_time" in call.data:
            start_time = _parse_time(call.data["start_time"])
            if start_time < min_start:
                start_time = min_start
        else:
            start_time = min_start
        if end_time <= start_time:
            raise HomeAssistantError("end_time must be after start_time")
        try:
            await coordinator.api.start_reservation(
                call.data["license_plate"], end_time, start_time=start_time
            )
        except NijmegenParkingError as err:
            raise HomeAssistantError(str(err)) from err
        await coordinator.async_request_refresh()

    async def handle_update_reservation(call: ServiceCall) -> None:
        coordinator = _get_coordinator_by_device(hass, call.data["device_id"])
        reservation_id = call.data["reservation_id"]
        new_plate = call.data.get("license_plate")
        new_start_raw = call.data.get("start_time")
        new_end_raw = call.data.get("end_time")

        if new_plate is None and new_start_raw is None and new_end_raw is None:
            raise HomeAssistantError(
                "Provide at least one of: license_plate, start_time, end_time"
            )

        # Look up current reservation values as defaults for omitted fields
        current = None
        if coordinator.data:
            current = next(
                (r for r in coordinator.data.reservations if r.id == reservation_id),
                None,
            )

        if new_plate is None:
            if current is None:
                raise HomeAssistantError(
                    "license_plate required: reservation not found in current data"
                )
            license_plate = current.license_plate
        else:
            license_plate = new_plate

        if new_start_raw is None:
            if current is None:
                raise HomeAssistantError(
                    "start_time required: reservation not found in current data"
                )
            start_time = current.start_time
        else:
            start_time = _parse_time(new_start_raw)

        if new_end_raw is None:
            if current is None:
                raise HomeAssistantError(
                    "end_time required: reservation not found in current data"
                )
            end_time = current.end_time
        else:
            end_time = _parse_time(new_end_raw)

        if end_time <= start_time:
            raise HomeAssistantError("end_time must be after start_time")

        try:
            await coordinator.api.end_reservation(reservation_id)
            await coordinator.api.start_reservation(
                license_plate, end_time, start_time=start_time
            )
        except NijmegenParkingError as err:
            raise HomeAssistantError(str(err)) from err
        await coordinator.async_request_refresh()

    async def handle_end_reservation(call: ServiceCall) -> None:
        coordinator = _get_coordinator_by_device(hass, call.data["device_id"])
        try:
            await coordinator.api.end_reservation(call.data["reservation_id"])
        except NijmegenParkingError as err:
            raise HomeAssistantError(str(err)) from err
        await coordinator.async_request_refresh()

    async def handle_list_reservations(call: ServiceCall) -> dict:
        coordinator = _get_coordinator_by_device(hass, call.data["device_id"])
        data, stale = await _refresh_data(coordinator)
        now = datetime.now(UTC)
        visible = [r for r in data.reservations if r.end_time > now]
        active = [r for r in visible if r.start_time <= now < r.end_time]
        future = [r for r in visible if r.start_time > now]
        favorite_by_plate = {f.license_plate: f.name for f in data.favorites}
        return {
            "count": len(visible),
            "active_count": len(active),
            "future_count": len(future),
            "reservations": [
                {
                    "id": r.id,
                    "license_plate": r.license_plate,
                    "start_time": r.start_time.isoformat(),
                    "end_time": r.end_time.isoformat(),
                    "is_active": r.start_time <= now < r.end_time,
                    "favorite_name": favorite_by_plate.get(r.license_plate),
                }
                for r in visible
            ],
            "stale": stale,
        }

    async def handle_add_favorite(call: ServiceCall) -> None:
        coordinator = _get_coordinator_by_device(hass, call.data["device_id"])
        try:
            await coordinator.api.add_favorite(
                call.data["license_plate"], call.data.get("name")
            )
        except NijmegenParkingError as err:
            raise HomeAssistantError(str(err)) from err
        await coordinator.async_request_refresh()

    async def handle_update_favorite(call: ServiceCall) -> None:
        coordinator = _get_coordinator_by_device(hass, call.data["device_id"])
        try:
            await coordinator.api.add_favorite(
                call.data["license_plate"], call.data.get("name")
            )
        except NijmegenParkingError as err:
            raise HomeAssistantError(str(err)) from err
        await coordinator.async_request_refresh()

    async def handle_remove_favorite(call: ServiceCall) -> None:
        coordinator = _get_coordinator_by_device(hass, call.data["device_id"])
        try:
            await coordinator.api.remove_favorite(call.data["license_plate"])
        except NijmegenParkingError as err:
            raise HomeAssistantError(str(err)) from err
        await coordinator.async_request_refresh()

    async def handle_list_favorites(call: ServiceCall) -> dict:
        coordinator = _get_coordinator_by_device(hass, call.data["device_id"])
        data, stale = await _refresh_data(coordinator)
        return {
            "count": len(data.favorites),
            "favorites": [
                {"license_plate": f.license_plate, "name": f.name}
                for f in data.favorites
            ],
            "stale": stale,
        }

    async def handle_get_status(call: ServiceCall) -> dict:
        coordinator = _get_coordinator_by_device(hass, call.data["device_id"])
        data, stale = await _refresh_data(coordinator)
        now = datetime.now(UTC)
        window = current_or_next_window(data.permit.zone_validity, now)
        return {
            "permit_id": data.permit.id,
            "remaining_balance_hours": round(data.permit.remaining_balance / 60, 2),
            "remaining_balance_minutes": data.permit.remaining_balance,
            "is_chargeable_now": is_currently_chargeable(
                data.permit.zone_validity, now
            ),
            "next_window_start": window.start.isoformat() if window else None,
            "next_window_end": window.end.isoformat() if window else None,
            "stale": stale,
        }

    async def handle_get_entry_info(call: ServiceCall) -> dict:
        coordinator = _get_coordinator_by_device(hass, call.data["device_id"])
        entry = coordinator._entry
        return {
            "permit_id": coordinator.data.permit.id if coordinator.data else None,
            "title": entry.title if entry is not None else "unknown",
        }

    hass.services.async_register(
        DOMAIN,
        "start_reservation",
        handle_start_reservation,
        schema=_START_RESERVATION_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        "update_reservation",
        handle_update_reservation,
        schema=_UPDATE_RESERVATION_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        "end_reservation",
        handle_end_reservation,
        schema=_END_RESERVATION_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        "list_reservations",
        handle_list_reservations,
        schema=_DEVICE_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        "add_favorite",
        handle_add_favorite,
        schema=_ADD_FAVORITE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        "update_favorite",
        handle_update_favorite,
        schema=_UPDATE_FAVORITE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        "remove_favorite",
        handle_remove_favorite,
        schema=_REMOVE_FAVORITE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        "list_favorites",
        handle_list_favorites,
        schema=_DEVICE_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        "get_status",
        handle_get_status,
        schema=_DEVICE_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        "get_entry_info",
        handle_get_entry_info,
        schema=_DEVICE_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
