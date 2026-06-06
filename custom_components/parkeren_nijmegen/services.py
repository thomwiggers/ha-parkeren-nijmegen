from __future__ import annotations

import logging
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN
from .coordinator import NijmegenCoordinator
from .exceptions import NijmegenParkingError

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

_END_RESERVATION_SCHEMA = vol.Schema(
    {
        vol.Required("device_id"): str,
        vol.Required("reservation_id"): str,
    }
)

_LIST_RESERVATIONS_SCHEMA = vol.Schema(
    {
        vol.Required("device_id"): str,
    }
)


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


def async_register_services(hass: HomeAssistant) -> None:
    async def handle_start_reservation(call: ServiceCall) -> None:
        coordinator = _get_coordinator_by_device(hass, call.data["device_id"])
        end_time = _parse_time(call.data["end_time"])
        start_time = (
            _parse_time(call.data["start_time"]) if "start_time" in call.data else None
        )
        try:
            await coordinator.api.start_reservation(
                call.data["license_plate"], end_time, start_time=start_time
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
        now = datetime.now(UTC)
        reservations = coordinator.data.reservations if coordinator.data else ()
        return {
            "reservations": [
                {
                    "id": r.id,
                    "license_plate": r.license_plate,
                    "start_time": r.start_time.isoformat(),
                    "end_time": r.end_time.isoformat(),
                    "is_active": r.start_time <= now < r.end_time,
                }
                for r in reservations
            ]
        }

    hass.services.async_register(
        DOMAIN,
        "start_reservation",
        handle_start_reservation,
        schema=_START_RESERVATION_SCHEMA,
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
        schema=_LIST_RESERVATIONS_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
