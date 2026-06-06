from __future__ import annotations

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN
from .coordinator import NijmegenCoordinator
from .exceptions import NijmegenParkingError

_TZ = ZoneInfo("Europe/Amsterdam")

_LOGGER = logging.getLogger(__name__)

_START_RESERVATION_SCHEMA = vol.Schema(
    {
        vol.Required("config_entry_id"): str,
        vol.Required("license_plate"): str,
        vol.Required("end_time"): str,
    }
)

_END_RESERVATION_SCHEMA = vol.Schema(
    {
        vol.Required("config_entry_id"): str,
        vol.Required("reservation_id"): str,
    }
)


def _get_coordinator(hass: HomeAssistant, entry_id: str) -> NijmegenCoordinator:
    coordinator = hass.data.get(DOMAIN, {}).get(entry_id)
    if coordinator is None:
        raise HomeAssistantError(f"No Parkeren Nijmegen entry found: {entry_id}")
    return coordinator


def async_register_services(hass: HomeAssistant) -> None:
    async def handle_start_reservation(call: ServiceCall) -> None:
        coordinator = _get_coordinator(hass, call.data["config_entry_id"])
        try:
            end_time = datetime.fromisoformat(call.data["end_time"])
        except ValueError as err:
            raise HomeAssistantError(f"Invalid end_time: {err}") from err
        if end_time.tzinfo is None:
            end_time = end_time.replace(tzinfo=_TZ)
        try:
            await coordinator.api.start_reservation(
                call.data["license_plate"], end_time
            )
        except NijmegenParkingError as err:
            raise HomeAssistantError(str(err)) from err
        await coordinator.async_request_refresh()

    async def handle_end_reservation(call: ServiceCall) -> None:
        coordinator = _get_coordinator(hass, call.data["config_entry_id"])
        try:
            await coordinator.api.end_reservation(call.data["reservation_id"])
        except NijmegenParkingError as err:
            raise HomeAssistantError(str(err)) from err
        await coordinator.async_request_refresh()

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
