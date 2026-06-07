from datetime import UTC

import pytest
from aioresponses import aioresponses

from custom_components.parkeren_nijmegen.api import NijmegenParkingAPI
from custom_components.parkeren_nijmegen.const import API_BASE, APP_BASE, BASE_URL
from custom_components.parkeren_nijmegen.exceptions import AuthError, ProviderError
from tests.conftest import (
    SAMPLE_BAD_LOGIN_RESPONSE,
    SAMPLE_LOGIN_RESPONSE,
    SAMPLE_PERMIT_DATA,
)

GETBASE_URL = f"{BASE_URL}{API_BASE}/login/getbase"
LOGIN_URL = f"{BASE_URL}{API_BASE}/login"
APP_ENV_URL = f"{BASE_URL}{APP_BASE}/app.env.js"


def test_normalize_plate():
    from custom_components.parkeren_nijmegen.api import _normalize_plate

    assert _normalize_plate("AB-12-CD") == "AB12CD"
    assert _normalize_plate("ab 12 cd") == "AB12CD"
    assert _normalize_plate("AB12CD") == "AB12CD"


async def test_fetch_all_success(api_client):
    with aioresponses() as m:
        m.post(GETBASE_URL, payload=SAMPLE_PERMIT_DATA)
        permit, reservations, favorites = await api_client.fetch_all()

    assert permit.id == "CARD-1"
    assert permit.remaining_balance == 120
    assert len(permit.zone_validity) == 1  # only IsFree=False block
    assert len(reservations) == 1
    assert reservations[0].id == "123"
    assert reservations[0].license_plate == "AB12CD"
    assert len(favorites) == 1
    assert favorites[0].license_plate == "XY99ZZ"
    assert favorites[0].name == "Family"


async def test_fetch_all_raises_auth_on_401(api_client):
    with aioresponses() as m:
        m.post(GETBASE_URL, status=401)
        with pytest.raises(AuthError):
            await api_client.fetch_all()


async def test_fetch_all_raises_provider_on_500_json(api_client):
    """500 with JSON body is a real provider error, not session expiry."""
    with aioresponses() as m:
        m.post(GETBASE_URL, status=500, payload={"error": "something"})
        with pytest.raises(ProviderError):
            await api_client.fetch_all()


async def test_fetch_all_reauths_on_500_html(api_client):
    """Core fix: 500+HTML triggers re-login and retry (issue #76)."""
    with aioresponses() as m:
        # First getbase call: Nijmegen session-expiry response
        m.post(
            GETBASE_URL,
            status=500,
            content_type="text/html; charset=utf-8",
            body="<html>Bezoekers App</html>",
        )
        # XSRF discovery during re-login
        xsrf_body = 'window.__env.xsrfCookieName = "Xsrf-DVSPortal"'
        m.get(APP_ENV_URL, status=200, body=xsrf_body)
        # Re-login succeeds
        m.post(LOGIN_URL, payload=SAMPLE_LOGIN_RESPONSE)
        # Retry getbase succeeds
        m.post(GETBASE_URL, payload=SAMPLE_PERMIT_DATA)

        permit, _, _ = await api_client.fetch_all()

    assert permit.remaining_balance == 120


async def test_fetch_all_raises_auth_if_retry_also_fails(api_client):
    """If re-auth succeeds but retry still returns 500+HTML, raise AuthError."""
    with aioresponses() as m:
        m.post(
            GETBASE_URL,
            status=500,
            content_type="text/html; charset=utf-8",
            body="<html></html>",
        )
        m.get(APP_ENV_URL, status=404)
        m.post(LOGIN_URL, payload=SAMPLE_LOGIN_RESPONSE)
        m.post(
            GETBASE_URL,
            status=500,
            content_type="text/html; charset=utf-8",
            body="<html></html>",
        )

        with pytest.raises(AuthError):
            await api_client.fetch_all()


async def test_login_sets_media_code(http_session):
    """Login with correct payload sets _permit_media_code from response."""
    api = NijmegenParkingAPI(http_session)
    with aioresponses() as m:
        xsrf_body = 'window.__env.xsrfCookieName = "Xsrf-DVSPortal"'
        m.get(APP_ENV_URL, status=200, body=xsrf_body)
        m.post(LOGIN_URL, payload=SAMPLE_LOGIN_RESPONSE)

        await api.login("334412", "8563")

    assert api._permit_media_code == "CARD-1"
    assert api._username == "334412"


async def test_login_raises_auth_on_bad_credentials(http_session):
    """LoginStatus 2 with ErrorMessage triggers AuthError."""
    api = NijmegenParkingAPI(http_session)
    with aioresponses() as m:
        m.get(APP_ENV_URL, status=404)
        m.post(LOGIN_URL, payload=SAMPLE_BAD_LOGIN_RESPONSE)

        with pytest.raises(AuthError):
            await api.login("334412", "wrongpass")


async def test_add_favorite_payload(api_client):
    """add_favorite sends updateLicensePlate as string and info field."""
    from unittest.mock import AsyncMock, patch

    captured = {}

    async def fake_post(endpoint, payload=None, **kwargs):
        captured["endpoint"] = endpoint
        captured["payload"] = payload
        return {}

    with patch.object(api_client, "_post", side_effect=fake_post):
        await api_client.add_favorite("AB-12-CD", "Jan")

    assert captured["endpoint"] == "/permitmedialicenseplate/upsert"
    sent = captured["payload"]
    assert sent["licensePlate"] == {"Value": "AB12CD", "Name": "Jan"}
    assert sent["updateLicensePlate"] == "AB12CD"
    assert sent["info"] == "Jan"
    assert sent["name"] == "Jan"


async def test_add_favorite_payload_no_name(api_client):
    """add_favorite without name uses normalized plate for name and info."""
    from unittest.mock import patch

    captured = {}

    async def fake_post(endpoint, payload=None, **kwargs):
        captured["payload"] = payload
        return {}

    with patch.object(api_client, "_post", side_effect=fake_post):
        await api_client.add_favorite("AB12CD")

    sent = captured["payload"]
    assert sent["updateLicensePlate"] == "AB12CD"
    assert sent["info"] == "AB12CD"


async def test_remove_favorite_payload(api_client):
    """remove_favorite sends licensePlate as string with Name and info fields."""
    from unittest.mock import patch

    captured = {}

    async def fake_post(endpoint, payload=None, **kwargs):
        captured["endpoint"] = endpoint
        captured["payload"] = payload
        return {}

    with patch.object(api_client, "_post", side_effect=fake_post):
        await api_client.remove_favorite("AB-12-CD")

    assert captured["endpoint"] == "/permitmedialicenseplate/remove"
    sent = captured["payload"]
    assert sent["licensePlate"] == "AB12CD"
    assert sent["Name"] == "AB12CD"
    assert sent["info"] == "AB12CD"


async def test_parse_ts_utc_z_suffix():
    """BlockTimes from real API use Z suffix UTC timestamps."""

    from custom_components.parkeren_nijmegen.api import _parse_ts

    dt = _parse_ts("2024-01-02T08:00:00Z")
    assert dt.tzinfo == UTC
    assert dt.hour == 8
    assert dt.day == 2
