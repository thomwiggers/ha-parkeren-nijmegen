# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
uv sync                        # install dev deps
uv run pytest                  # run all tests
uv run pytest tests/test_api.py::test_fetch_all_success -v  # single test
uv run ruff check custom_components/ tests/   # lint
uv run ruff format custom_components/ tests/  # format
```

## Architecture

Standalone Home Assistant custom integration for Nijmegen visitor parking. No external library — all HTTP logic lives here.

**Key design constraint:** Nijmegen's DVS Portal returns `HTTP 500 + Content-Type: text/html` when the session cookie expires (not 401/403). `api.py:_post()` detects this and re-logs in silently before retrying. This is the core fix the integration exists to provide.

### Auth flow

Cookie-based (not token). `login()` POSTs to `/DVSPortal/api/login` with `{identifier, loginMethod: 2, password, permitMediaTypeID}`. The server sets a `DVS-Cookie` session cookie and an `Xsrf-DVSPortal` CSRF cookie on the response. The XSRF cookie name is discovered from `/DVSPortal/app.env.js` before login. All subsequent requests carry the cookies automatically (aiohttp jar) plus an explicit `X-XSRF-TOKEN` header whose value is URL-decoded from the cookie.

### Module responsibilities

| File | Responsibility |
|------|---------------|
| `api.py` | All HTTP: XSRF discovery, login, `_post` with 500+HTML re-auth, fetch/mutate |
| `coordinator.py` | `DataUpdateCoordinator` — polls every 5 min, converts `AuthError` → `async_start_reauth` |
| `sensor.py` | Seven entities: active/future reservations, remaining time (hours), zone state, chargeable window timestamps, favorites |
| `config_flow.py` | Config flow + reauth flow; persists `permit_media_code` and `permit_media_type_id` |
| `__init__.py` | Entry setup (login → coordinator → sensors → services), teardown |
| `services.py` | `start_reservation` / `end_reservation` HA service handlers |
| `models.py` | Frozen dataclasses: `ZoneBlock`, `Permit`, `Reservation`, `Favorite`, `CoordinatorData` |

### API response shape

Login and `getbase` both return `{Permits: [{ZoneCode, BlockTimes, PermitMedias: [{TypeID, Code, Balance, ActiveReservations, LicensePlates}]}]}`. The integration always uses `Permits[0]` and `PermitMedias[0]`. Timestamps from the API are UTC with a `Z` suffix; they're parsed to timezone-aware `datetime` objects and stored as UTC throughout.

### Testing

Uses `pytest-homeassistant-custom-component` + `aioresponses`. All tests are async (`asyncio_mode = auto`). Fixtures in `tests/conftest.py` include `SAMPLE_PERMIT_DATA` (real API shape) and `api_client` (pre-authenticated API instance with `permit_media_type_id=7`).
