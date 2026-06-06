from __future__ import annotations

from datetime import UTC, datetime

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import NijmegenCoordinator, is_currently_chargeable


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: NijmegenCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        ActiveReservationsSensor(coordinator, entry),
        RemainingBalanceSensor(coordinator, entry),
        ZoneStateSensor(coordinator, entry),
    ])


class _NijmegenSensor(CoordinatorEntity[NijmegenCoordinator], SensorEntity):
    _attr_has_entity_name = True

    def __init__(
        self, coordinator: NijmegenCoordinator, entry: ConfigEntry, key: str
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._entry = entry


class ActiveReservationsSensor(_NijmegenSensor):
    _attr_name = "Actieve reserveringen"
    _attr_icon = "mdi:car"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: NijmegenCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "active_reservations")

    @property
    def native_value(self) -> int:
        return len(self.coordinator.data.reservations) if self.coordinator.data else 0


class RemainingBalanceSensor(_NijmegenSensor):
    _attr_name = "Resterende minuten"
    _attr_native_unit_of_measurement = "min"
    _attr_icon = "mdi:timer-outline"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: NijmegenCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "remaining_balance")

    @property
    def native_value(self) -> int:
        if self.coordinator.data:
            return self.coordinator.data.permit.remaining_balance
        return 0


class ZoneStateSensor(_NijmegenSensor):
    _attr_name = "Parkeertijdvak"
    _attr_icon = "mdi:clock-outline"

    def __init__(self, coordinator: NijmegenCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "zone_state")

    @property
    def native_value(self) -> str:
        if not self.coordinator.data:
            return "unknown"
        now = datetime.now(UTC)
        return "betaald" if is_currently_chargeable(
            self.coordinator.data.permit.zone_validity, now
        ) else "gratis"
