from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ZoneBlock:
    start: datetime  # UTC-aware
    end: datetime    # UTC-aware


@dataclass(frozen=True)
class Permit:
    id: str
    remaining_balance: int   # minutes
    zone_validity: tuple[ZoneBlock, ...]  # chargeable windows only (IsFree=False)


@dataclass(frozen=True)
class Reservation:
    id: str
    license_plate: str      # normalized: uppercase, no dashes/spaces
    start_time: datetime    # UTC-aware
    end_time: datetime      # UTC-aware


@dataclass(frozen=True)
class Favorite:
    license_plate: str      # normalized
    name: str


@dataclass(frozen=True)
class CoordinatorData:
    permit: Permit
    reservations: tuple[Reservation, ...]
    favorites: tuple[Favorite, ...]
