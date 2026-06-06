# ha-parkeren-nijmegen

Home Assistant custom integration for **Nijmegen** visitor parking (parkeerproducten.nijmegen.nl).

## Why a separate integration?

The generic [ha_City-Visitor-Parking](https://github.com/sir-Unknown/ha_City-Visitor-Parking) integration (backed by [pyCityVisitorParking](https://github.com/sir-Unknown/pyCityVisitorParking)) supports many Dutch municipalities. Nijmegen's DVS Portal has a quirk that breaks re-authentication in that library: when the session expires, the server returns **HTTP 500 with a `text/html` body** instead of 401/403. The library only re-authenticates on 401/403, so expired sessions are never recovered ([issue #76](https://github.com/sir-Unknown/pyCityVisitorParking/issues/76)).

This integration handles that response directly and silently re-logs in, so sessions recover without user intervention.

## Features

**Sensors:**

| Sensor | Description |
|--------|-------------|
| Actieve reserveringen | Number of currently active reservations; attributes include plate, start/end time per reservation |
| Geplande reserveringen | Number of future (not yet started) reservations |
| Resterende parkeertijd | Remaining balance in hours; attributes include raw minutes, active count, next end time |
| Parkeertijdvak | `betaald` or `gratis`; attributes include next window start/end |
| Start betaald tijdvak | Timestamp of current/next chargeable window start *(diagnostic, disabled by default)* |
| Einde betaald tijdvak | Timestamp of current/next chargeable window end *(diagnostic, disabled by default)* |
| Favorieten | Number of saved licence plates; attributes list all plates and names |

**Actions:**
- `parkeren_nijmegen.start_reservation` — start a visitor parking reservation
- `parkeren_nijmegen.end_reservation` — end an active reservation

**Other:**
- Config flow with re-authentication support
- No external library dependencies

## Installation

**HACS (recommended):**
1. HACS → ⋮ → Custom repositories → add `https://github.com/thomwiggers/ha-parkeren-nijmegen`, category *Integration*
2. Install, restart HA
3. Settings → Integrations → Add → *Parkeren Nijmegen*

**Manual:**
Copy `custom_components/parkeren_nijmegen/` to `<config>/custom_components/parkeren_nijmegen/`, restart HA, then add the integration.

## Configuration

Enter your **meldnummer** (account number) and **PIN-code** from the Nijmegen parking portal. The integration stores your permit media code so it survives re-authentication.

## Services

### `parkeren_nijmegen.start_reservation`

| Field | Description |
|-------|-------------|
| `config_entry_id` | The integration entry |
| `license_plate` | Visitor licence plate (e.g. `AB12CD`) |
| `end_time` | When the reservation ends (ISO 8601 datetime) |

### `parkeren_nijmegen.end_reservation`

| Field | Description |
|-------|-------------|
| `config_entry_id` | The integration entry |
| `reservation_id` | ID from the active reservations sensor |

## Credits

Inspired by [ha_City-Visitor-Parking](https://github.com/sir-Unknown/ha_City-Visitor-Parking) and [pyCityVisitorParking](https://github.com/sir-Unknown/pyCityVisitorParking) by [@sir-Unknown](https://github.com/sir-Unknown).
