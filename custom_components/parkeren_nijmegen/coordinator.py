from __future__ import annotations

import logging
from datetime import datetime

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import NijmegenParkingAPI
from .const import DOMAIN, SCAN_INTERVAL
from .exceptions import AuthError, ProviderError
from .models import CoordinatorData, ZoneBlock

_LOGGER = logging.getLogger(__name__)


def is_currently_chargeable(
    zone_validity: tuple[ZoneBlock, ...], now: datetime
) -> bool:
    return any(block.start <= now < block.end for block in zone_validity)


class NijmegenCoordinator(DataUpdateCoordinator[CoordinatorData]):
    def __init__(
        self,
        hass: HomeAssistant,
        api: NijmegenParkingAPI,
        entry: ConfigEntry | None = None,
    ) -> None:
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=SCAN_INTERVAL)
        self.api = api
        self._entry = entry

    async def _async_update_data(self) -> CoordinatorData:
        try:
            permit, reservations, favorites = await self.api.fetch_all()
        except AuthError as err:
            if self._entry is not None:
                self._entry.async_start_reauth(self.hass)
            raise UpdateFailed(f"Authentication failed: {err}") from err
        except ProviderError as err:
            raise UpdateFailed(f"Provider error: {err}") from err

        return CoordinatorData(
            permit=permit,
            reservations=tuple(reservations),
            favorites=tuple(favorites),
        )
