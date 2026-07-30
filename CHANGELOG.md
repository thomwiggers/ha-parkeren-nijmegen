# CHANGELOG


## v0.2.0 (2026-07-30)

### Documentation

- Add release-automation design spec
  ([`254dc68`](https://github.com/thomwiggers/ha-parkeren-nijmegen/commit/254dc68bdde640966cffb8863f27e86f23707ba1))

Design for cutting GitHub Releases via python-semantic-release on squash-merged,
  conventional-commit-titled PRs to main.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>

Claude-Session: https://claude.ai/code/session_0126HFtFUWGY7gxxsPg35iX9

### Features

- Cut releases automatically via python-semantic-release
  ([`8a20e03`](https://github.com/thomwiggers/ha-parkeren-nijmegen/commit/8a20e0305c260402f8646d5f10ae72a0bdad81cc))

Adds a release job to ci.yaml that runs python-semantic-release on push to main after tests pass,
  parsing conventional-commit-typed commits to bump version (pyproject.toml + manifest.json), update
  CHANGELOG.md, tag, and create the GitHub Release.

Adds pr-title-lint.yaml to enforce conventional-commit PR titles, since squash-merge (to be enabled
  as a repo setting separately) turns each PR title into main's commit message that semantic-release
  reads.

Documents the convention in CLAUDE.md.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>

Claude-Session: https://claude.ai/code/session_0126HFtFUWGY7gxxsPg35iX9


## v0.1.0 (2026-07-30)

### Bug Fixes

- Correct upsert/remove payloads for favorite license plates
  ([`0d66e85`](https://github.com/thomwiggers/ha-parkeren-nijmegen/commit/0d66e85359caabf36ebded0f47f1ac22eab45c9c))

updateLicensePlate must be a string (not null), info field is required. remove_favorite also needs
  info field and capital-N Name field.

Discovered by probing the real DVS Portal API.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- Handle naive end_time, validate fromisoformat, add missing tests
  ([`374c369`](https://github.com/thomwiggers/ha-parkeren-nijmegen/commit/374c369532b07a50502bfe1b7d561543eb8d2a1a))

- services.py: wrap fromisoformat in try/except ValueError → HomeAssistantError - services.py:
  attach Amsterdam timezone to naive end_time from HA datetime selector - test_services.py: assert
  end_time arg is timezone-aware; add end_reservation error test - api.py: keep comment explaining
  500+HTML is session expiry behavior - ruff format pass on several files

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- Move brand images to brand/ per HA 2026.3 convention
  ([`a985c5e`](https://github.com/thomwiggers/ha-parkeren-nijmegen/commit/a985c5e466f827b3da5f8edf6a6b8da547a0de0f))

HA 2026.3+ serves custom integration logos from brand/ not images/. Add icon.png, logo.png (256px)
  and @2x variants (512px). Keep images/logo.svg as SVG source.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- Pin remaining parking time display unit to hours
  ([`2d0cf05`](https://github.com/thomwiggers/ha-parkeren-nijmegen/commit/2d0cf05e9bea48b13917fbb618f3ff7c292ab0b5))

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- Retry on 401 like 500+HTML (session expiry)
  ([`cca1046`](https://github.com/thomwiggers/ha-parkeren-nijmegen/commit/cca1046ee918e41404d3d3224c461397a183dd03))

Some endpoints (permitmedialicenseplate/*) return 401 on session expiry instead of 500+HTML. Extend
  the re-login+retry logic to cover 401 too.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- Update API client to match real Nijmegen DVS Portal format
  ([`c0b84f7`](https://github.com/thomwiggers/ha-parkeren-nijmegen/commit/c0b84f7d42c375c14e6e964f913212176229a043))

Cookie auth (DVS-Cookie) replaces token auth; login payload uses 'identifier' field; response uses
  'Permits' (plural list) not 'Permit'; UTC Z-suffix timestamps handled; LoginStatus 2 /
  ErrorMessage triggers AuthError; tests and conftest updated accordingly.

- Use DeviceEntryType.SERVICE for service-type device registration
  ([`963cc1e`](https://github.com/thomwiggers/ha-parkeren-nijmegen/commit/963cc1e15023580c56305449ec29430f10e8549c))

Makes integration show as "1 service" in HA integrations overview, matching the display style of
  ha_City-Visitor-Parking.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

### Documentation

- Add CLAUDE.md with architecture and dev commands
  ([`62e7205`](https://github.com/thomwiggers/ha-parkeren-nijmegen/commit/62e72051a068c2a6d926281e23de8d16f855f392))

- Add README with installation, services, and upstream credits
  ([`e0c34b5`](https://github.com/thomwiggers/ha-parkeren-nijmegen/commit/e0c34b5cb8dd4d9c46eb90b8ad645d9fa103e1da))

- Update README and CLAUDE.md for expanded sensor set
  ([`678632a`](https://github.com/thomwiggers/ha-parkeren-nijmegen/commit/678632aa73e202f57b90523206ebe644e2260730))

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

### Features

- Add config flow with username/password and reauth support
  ([`7633ddd`](https://github.com/thomwiggers/ha-parkeren-nijmegen/commit/7633ddde5febbf80ab9c288f93810d031113cee4))

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- Add coordinator, sensors, and integration setup
  ([`8c4daa3`](https://github.com/thomwiggers/ha-parkeren-nijmegen/commit/8c4daa308de3ad49dffbb8f25c6f6a17601be8ea))

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- Add integration logo icon
  ([`9905e71`](https://github.com/thomwiggers/ha-parkeren-nijmegen/commit/9905e713356205ca79e16a337842714aa3e4242e))

Blue parking sign with Nijmegen red crown header. Crown references the city's Imperial Free City
  heraldry. 256x256 PNG + SVG source.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- Add NijmegenParkingAPI with re-auth on 500+HTML (fixes issue #76)
  ([`8504cae`](https://github.com/thomwiggers/ha-parkeren-nijmegen/commit/8504cae8ffdf18a34a6ddbced7ca95b5b0021581))

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- Add sensors for chargeable windows, favorites, future reservations
  ([`222535a`](https://github.com/thomwiggers/ha-parkeren-nijmegen/commit/222535a67199dc3e7208ab2df684a27631f3c6df))

- DeviceInfo groups all entities under one device - Manufacturer set to "Bezoekersparkeren Nijmegen"
  - ActiveReservationsSensor: computed from start/end times, extra attrs - FutureReservationsSensor:
  reservations not yet started - RemainingBalanceSensor: hours (DURATION class), extra attrs -
  ZoneStateSensor: adds next window start/end to extra attrs - ChargeableStartSensor /
  ChargeableEndSensor: diagnostic timestamps - FavoritesSensor: count + license plate list in extra
  attrs - current_or_next_window() helper in coordinator

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- Add start_reservation and end_reservation services
  ([`6b53d0b`](https://github.com/thomwiggers/ha-parkeren-nijmegen/commit/6b53d0b63a6153dc47513c7accf475045c77214f))

Registers two HA services (start_reservation, end_reservation) with voluptuous schemas, wrapping
  coordinator.api calls and raising HomeAssistantError on NijmegenParkingError. Services are
  registered once on first entry load and removed when last entry is unloaded.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- Complete service set matching ha_City-Visitor-Parking
  ([`0cbb97c`](https://github.com/thomwiggers/ha-parkeren-nijmegen/commit/0cbb97cb7cbaa0d2eb3ff05af9437baa68ad3f52))

New services: update_reservation (end+recreate), add_favorite, update_favorite, remove_favorite,
  list_favorites, get_status, get_entry_info.

Improvements to existing services: - start_reservation: clamp start to now+1min, validate end>start
  - list_reservations: force-refresh, richer response (count/active_count/ future_count/stale),
  cross-reference favorites for favorite_name - update_reservation: looks up current reservation
  from coordinator data so only changed fields need to be provided

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- Initial project scaffold with models and exceptions
  ([`c223660`](https://github.com/thomwiggers/ha-parkeren-nijmegen/commit/c223660a67706e6c713e1ecf9c4eb4a6b3d3bcd7))

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- Switch services to device_id, add start_time and list_reservations
  ([`aa74dfc`](https://github.com/thomwiggers/ha-parkeren-nijmegen/commit/aa74dfc3c6c77d452c736b594038650afb410a29))

- start_reservation and end_reservation now target a device_id instead of config_entry_id; device
  lookup resolves to coordinator via registry - start_reservation accepts optional start_time
  (defaults to now) - new list_reservations service returns all reservations with is_active flag -
  api.start_reservation gains optional start_time parameter

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

### Refactoring

- Expose public properties on API, persist media code on reauth
  ([`f658164`](https://github.com/thomwiggers/ha-parkeren-nijmegen/commit/f65816416ef2f58e5f2df616684f640d28df0ad9))

- api.py: add permit_media_code/permit_media_type_id properties; accept as constructor kwargs
  instead of requiring post-init private writes - __init__.py: use constructor kwargs instead of
  private attribute access - config_flow.py: use public properties; persist validated
  permit_media_code and permit_media_type_id on reauth so stale values don't survive card changes -
  strings.json: add reauth_successful abort and service translations - test_config_flow.py: update
  mocks to set public properties

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
