from __future__ import annotations

from datetime import UTC, datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import (
    NijmegenCoordinator,
    current_or_next_window,
    is_currently_chargeable,
)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: NijmegenCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            ActiveReservationsSensor(coordinator, entry),
            FutureReservationsSensor(coordinator, entry),
            RemainingBalanceSensor(coordinator, entry),
            ZoneStateSensor(coordinator, entry),
            ChargeableStartSensor(coordinator, entry),
            ChargeableEndSensor(coordinator, entry),
            FavoritesSensor(coordinator, entry),
        ]
    )


class _NijmegenSensor(CoordinatorEntity[NijmegenCoordinator], SensorEntity):
    _attr_has_entity_name = True

    def __init__(
        self, coordinator: NijmegenCoordinator, entry: ConfigEntry, key: str
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._entry = entry
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="Bezoekersparkeren Nijmegen",
            model="DVS Parkeerportal",
            entry_type=DeviceEntryType.SERVICE,
        )


class ActiveReservationsSensor(_NijmegenSensor):
    _attr_name = "Actieve reserveringen"
    _attr_icon = "mdi:car"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: NijmegenCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "active_reservations")

    @property
    def native_value(self) -> int:
        if not self.coordinator.data:
            return 0
        now = datetime.now(UTC)
        return sum(
            1
            for r in self.coordinator.data.reservations
            if r.start_time <= now < r.end_time
        )

    @property
    def extra_state_attributes(self) -> dict:
        if not self.coordinator.data:
            return {}
        now = datetime.now(UTC)
        active = [
            r
            for r in self.coordinator.data.reservations
            if r.start_time <= now < r.end_time
        ]
        return {
            "reservations": [
                {
                    "id": r.id,
                    "license_plate": r.license_plate,
                    "start_time": r.start_time.isoformat(),
                    "end_time": r.end_time.isoformat(),
                }
                for r in active
            ]
        }


class FutureReservationsSensor(_NijmegenSensor):
    _attr_name = "Geplande reserveringen"
    _attr_icon = "mdi:car-clock"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: NijmegenCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "future_reservations")

    @property
    def native_value(self) -> int:
        if not self.coordinator.data:
            return 0
        now = datetime.now(UTC)
        return sum(1 for r in self.coordinator.data.reservations if r.start_time > now)


class RemainingBalanceSensor(_NijmegenSensor):
    _attr_name = "Resterende parkeertijd"
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.HOURS
    _attr_suggested_unit_of_measurement = UnitOfTime.HOURS
    _attr_suggested_display_precision = 2
    _attr_icon = "mdi:timer-outline"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: NijmegenCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "remaining_balance")

    @property
    def native_value(self) -> float:
        if not self.coordinator.data:
            return 0.0
        return round(self.coordinator.data.permit.remaining_balance / 60, 2)

    @property
    def extra_state_attributes(self) -> dict:
        if not self.coordinator.data:
            return {}
        now = datetime.now(UTC)
        active = [
            r
            for r in self.coordinator.data.reservations
            if r.start_time <= now < r.end_time
        ]
        next_end = min((r.end_time for r in active), default=None)
        return {
            "remaining_minutes": self.coordinator.data.permit.remaining_balance,
            "active_reservations": len(active),
            "has_active_reservation": len(active) > 0,
            "next_end_time": next_end.isoformat() if next_end else None,
        }


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
        return (
            "betaald"
            if is_currently_chargeable(self.coordinator.data.permit.zone_validity, now)
            else "gratis"
        )

    @property
    def extra_state_attributes(self) -> dict:
        if not self.coordinator.data:
            return {}
        now = datetime.now(UTC)
        window = current_or_next_window(self.coordinator.data.permit.zone_validity, now)
        return {
            "is_chargeable_now": is_currently_chargeable(
                self.coordinator.data.permit.zone_validity, now
            ),
            "next_window_start": window.start.isoformat() if window else None,
            "next_window_end": window.end.isoformat() if window else None,
        }


class ChargeableStartSensor(_NijmegenSensor):
    _attr_name = "Start betaald tijdvak"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: NijmegenCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "chargeable_start")

    @property
    def native_value(self) -> datetime | None:
        if not self.coordinator.data:
            return None
        now = datetime.now(UTC)
        window = current_or_next_window(self.coordinator.data.permit.zone_validity, now)
        return window.start if window else None


class ChargeableEndSensor(_NijmegenSensor):
    _attr_name = "Einde betaald tijdvak"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: NijmegenCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "chargeable_end")

    @property
    def native_value(self) -> datetime | None:
        if not self.coordinator.data:
            return None
        now = datetime.now(UTC)
        window = current_or_next_window(self.coordinator.data.permit.zone_validity, now)
        return window.end if window else None


class FavoritesSensor(_NijmegenSensor):
    _attr_name = "Favorieten"
    _attr_icon = "mdi:star"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: NijmegenCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "favorites")

    @property
    def native_value(self) -> int:
        return len(self.coordinator.data.favorites) if self.coordinator.data else 0

    @property
    def extra_state_attributes(self) -> dict:
        if not self.coordinator.data:
            return {}
        return {
            "license_plates": [
                {"license_plate": f.license_plate, "name": f.name}
                for f in self.coordinator.data.favorites
            ]
        }
