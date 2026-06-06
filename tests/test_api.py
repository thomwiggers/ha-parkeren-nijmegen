import pytest
from aioresponses import aioresponses

from custom_components.parkeren_nijmegen.api import NijmegenParkingAPI
from custom_components.parkeren_nijmegen.const import API_BASE, APP_BASE, BASE_URL
from custom_components.parkeren_nijmegen.exceptions import AuthError, ProviderError
from tests.conftest import SAMPLE_LOGIN_RESPONSE, SAMPLE_PERMIT_DATA

GETBASE_URL = f"{BASE_URL}{API_BASE}/login/getbase"
LOGIN_URL = f"{BASE_URL}{API_BASE}/login"
APP_ENV_URL = f"{BASE_URL}{APP_BASE}/app.env.js"
APP_HTML_URL = f"{BASE_URL}{APP_BASE}/"


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


async def test_fetch_all_reauths_on_500_html(api_client, http_session):
    """Core fix: 500+HTML triggers re-login and retry (issue #76)."""
    with aioresponses() as m:
        # First getbase call: Nijmegen session-expiry response
        m.post(
            GETBASE_URL,
            status=500,
            content_type="text/html; charset=utf-8",
            body="<html>Bezoekers App</html>",
        )
        # XSRF bootstrap during re-login
        m.get(
            APP_ENV_URL,
            status=200,
            body='window.__env.xsrfCookieName = "XSRF-TOKEN"',
        )
        m.get(APP_HTML_URL, status=200, body="<html></html>")
        # Re-login succeeds
        m.post(LOGIN_URL, payload=SAMPLE_LOGIN_RESPONSE)
        # Retry getbase succeeds
        m.post(GETBASE_URL, payload=SAMPLE_PERMIT_DATA)

        permit, reservations, favorites = await api_client.fetch_all()

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
        m.get(APP_HTML_URL, status=404)
        m.post(LOGIN_URL, payload=SAMPLE_LOGIN_RESPONSE)
        m.post(
            GETBASE_URL,
            status=500,
            content_type="text/html; charset=utf-8",
            body="<html></html>",
        )

        with pytest.raises(AuthError):
            await api_client.fetch_all()


async def test_login_sets_token(http_session):
    api = NijmegenParkingAPI(http_session)
    with aioresponses() as m:
        m.get(
            APP_ENV_URL,
            status=200,
            body='window.__env.xsrfCookieName = "XSRF-TOKEN"',
        )
        m.get(APP_HTML_URL, status=200, body="<html></html>")
        m.post(LOGIN_URL, payload=SAMPLE_LOGIN_RESPONSE)

        await api.login("user", "pass")

    assert api._token == "test-token-abc"
    assert api._permit_media_code == "CARD-1"


async def test_login_raises_auth_on_bad_credentials(http_session):
    api = NijmegenParkingAPI(http_session)
    with aioresponses() as m:
        m.get(APP_ENV_URL, status=404)
        m.get(APP_HTML_URL, status=404)
        m.post(
            LOGIN_URL,
            payload={"LoginStatus": 1, "Token": None, "ErrorMessage": "Invalid"},
        )

        with pytest.raises(AuthError):
            await api.login("user", "wrongpass")
