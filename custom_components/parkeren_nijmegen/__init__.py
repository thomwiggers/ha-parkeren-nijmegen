from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client

from .api import NijmegenParkingAPI
from .const import (
    CONF_PASSWORD,
    CONF_PERMIT_MEDIA_CODE,
    CONF_PERMIT_MEDIA_TYPE_ID,
    CONF_USERNAME,
    DOMAIN,
)
from .coordinator import NijmegenCoordinator
from .exceptions import AuthError
from .services import async_register_services

PLATFORMS = ["sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    session = aiohttp_client.async_get_clientsession(hass)
    api = NijmegenParkingAPI(session)
    api._permit_media_code = entry.data.get(CONF_PERMIT_MEDIA_CODE)
    api._permit_media_type_id = int(entry.data.get(CONF_PERMIT_MEDIA_TYPE_ID, 7))

    try:
        await api.login(entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD])
    except AuthError:
        entry.async_start_reauth(hass)
        return False

    coordinator = NijmegenCoordinator(hass, api, entry=entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    if not hass.services.has_service(DOMAIN, "start_reservation"):
        async_register_services(hass)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        if not hass.data.get(DOMAIN):
            hass.services.async_remove(DOMAIN, "start_reservation")
            hass.services.async_remove(DOMAIN, "end_reservation")
    return unloaded
