from __future__ import annotations

import re
import urllib.parse
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import aiohttp
from yarl import URL

from .const import API_BASE, APP_BASE, BASE_URL
from .exceptions import AuthError, ProviderError
from .models import Favorite, Permit, Reservation, ZoneBlock

_XSRF_RE = re.compile(r"window\.__env\.xsrfCookieName\s*=\s*['\"]([^'\"]+)['\"]")
_TZ = ZoneInfo("Europe/Amsterdam")
_DEFAULT_HEADERS = {
    "Accept": "application/json",
    "User-Agent": "parkeren-nijmegen-ha/0.1",
}
_DEFAULT_PERMIT_MEDIA_TYPE_ID = 7  # Nijmegen uses "Meldnummer" type ID 7


def _normalize_plate(plate: str) -> str:
    return re.sub(r"[\s\-]", "", plate).upper()


def _parse_ts(value: str) -> datetime:
    """Parse provider timestamp (UTC Z-suffix or offset-aware) to UTC datetime."""
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    parsed = datetime.fromisoformat(raw)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=_TZ, fold=0)
    return parsed.astimezone(UTC)


def _format_ts(dt: datetime) -> str:
    """Format UTC datetime as Amsterdam local time with milliseconds for API calls."""
    return dt.astimezone(_TZ).isoformat(timespec="milliseconds")


class NijmegenParkingAPI:
    def __init__(self, session: aiohttp.ClientSession) -> None:
        self._session = session
        self._xsrf_cookie_name: str = "Xsrf-DVSPortal"  # discovered from app.env.js
        self._username: str | None = None
        self._password: str | None = None
        self._permit_media_type_id: int = _DEFAULT_PERMIT_MEDIA_TYPE_ID
        self._permit_media_code: str | None = None

    async def _discover_xsrf_cookie_name(self) -> None:
        """Parse app.env.js to discover the XSRF cookie name for this deployment."""
        timeout = aiohttp.ClientTimeout(total=10)
        try:
            async with self._session.get(
                f"{BASE_URL}{APP_BASE}/app.env.js", timeout=timeout
            ) as resp:
                if resp.status == 200:
                    match = _XSRF_RE.search(await resp.text())
                    if match:
                        self._xsrf_cookie_name = match.group(1)
        except Exception:
            pass

    def _get_xsrf_token(self) -> str | None:
        cookies = self._session.cookie_jar.filter_cookies(URL(BASE_URL))
        cookie = cookies.get(self._xsrf_cookie_name)
        if cookie is None:
            return None
        # Cookie value may be URL-encoded
        return urllib.parse.unquote(cookie.value)

    async def login(self, username: str, password: str) -> None:
        """Authenticate against Nijmegen DVS Portal.

        Sets session cookies for subsequent calls.
        """
        self._username = username
        self._password = password
        await self._discover_xsrf_cookie_name()

        headers = {**_DEFAULT_HEADERS}
        xsrf = self._get_xsrf_token()
        if xsrf:
            headers["X-XSRF-TOKEN"] = xsrf

        payload = {
            "identifier": username,
            "loginMethod": 2,
            "password": password,
            "otp": None,
            "resetCode": None,
            "asIdentifier": None,
            "zipCode": None,
            "permitMediaTypeID": self._permit_media_type_id,
        }
        async with self._session.post(
            f"{BASE_URL}{API_BASE}/login", json=payload, headers=headers
        ) as resp:
            if resp.status in (401, 403):
                raise AuthError("Invalid credentials")
            if resp.status >= 400:
                raise ProviderError(f"Login failed: {resp.status}")
            data = await resp.json(content_type=None)

        # LoginStatus 2 = wrong credentials; ErrorMessage set = error
        if data.get("LoginStatus") == 2 or data.get("ErrorMessage"):
            msg = data.get("ErrorMessage", "unknown error")
            raise AuthError(f"Login failed: {msg}")

        # Cache permit media code from login response
        permits = data.get("Permits", [])
        if permits:
            medias = permits[0].get("PermitMedias", [])
            if medias and isinstance(medias[0], dict):
                self._permit_media_code = (
                    medias[0].get("Code") or self._permit_media_code
                )

    async def _post(
        self, endpoint: str, payload: dict | None = None, *, _retry: bool = True
    ) -> dict:
        """Make an authenticated POST request.

        Auth is via session cookie (DVS-Cookie).
        """
        headers = {**_DEFAULT_HEADERS}
        xsrf = self._get_xsrf_token()
        if xsrf:
            headers["X-XSRF-TOKEN"] = xsrf

        async with self._session.post(
            f"{BASE_URL}{API_BASE}{endpoint}",
            json=payload if payload is not None else {},
            headers=headers,
        ) as resp:
            content_type = resp.headers.get("Content-Type", "")
            if resp.status in (401, 403):
                raise AuthError("Authentication failed")
            if resp.status == 500 and "text/html" in content_type:
                # Nijmegen returns 500+HTML when the session cookie has expired.
                # pyCityVisitorParking only checks 401/403, so re-auth
                # never fires (issue #76).
                if _retry and self._username and self._password:
                    await self.login(self._username, self._password)
                    return await self._post(endpoint, payload, _retry=False)
                raise AuthError("Session expired and re-authentication failed")
            if not resp.ok:
                raise ProviderError(f"Request failed: {resp.status}")
            return await resp.json(content_type=None)

    def _extract_permit(self, data: dict) -> dict:
        permits = data.get("Permits")
        if isinstance(permits, list) and permits and isinstance(permits[0], dict):
            return permits[0]
        raise ProviderError("Response did not include permit data")

    def _cache_media_defaults(self, permit: dict) -> None:
        medias = permit.get("PermitMedias", [])
        if medias and isinstance(medias[0], dict):
            media = medias[0]
            if media.get("TypeID") is not None:
                self._permit_media_type_id = int(media["TypeID"])
            if media.get("Code"):
                self._permit_media_code = str(media["Code"]).strip()

    def _map_permit(self, permit: dict) -> Permit:
        medias = permit.get("PermitMedias", [])
        media = medias[0] if medias else {}
        permit_id = str(media.get("Code") or permit.get("ZoneCode") or "permit")
        balance = int(media.get("Balance") or 0)
        blocks = []
        for b in permit.get("BlockTimes", []):
            if b.get("IsFree") is True:
                continue
            try:
                start = _parse_ts(b["ValidFrom"])
                end = _parse_ts(b["ValidUntil"])
                blocks.append(ZoneBlock(start=start, end=end))
            except (KeyError, ValueError):
                continue
        return Permit(
            id=permit_id, remaining_balance=balance, zone_validity=tuple(blocks)
        )

    def _map_reservations(self, permit: dict) -> list[Reservation]:
        medias = permit.get("PermitMedias", [])
        media = medias[0] if medias else {}
        result = []
        for r in media.get("ActiveReservations", []):
            plate_info = r.get("LicensePlate", {})
            plate_raw = plate_info.get("Value") or plate_info.get("DisplayValue", "")
            try:
                result.append(
                    Reservation(
                        id=str(r["ReservationID"]),
                        license_plate=_normalize_plate(plate_raw),
                        start_time=_parse_ts(r["ValidFrom"]),
                        end_time=_parse_ts(r["ValidUntil"]),
                    )
                )
            except (KeyError, ValueError):
                continue
        return result

    def _map_favorites(self, permit: dict) -> list[Favorite]:
        medias = permit.get("PermitMedias", [])
        media = medias[0] if medias else {}
        result = []
        for lp in media.get("LicensePlates", []):
            value = lp.get("Value", "")
            if not value:
                continue
            result.append(
                Favorite(
                    license_plate=_normalize_plate(value),
                    name=lp.get("Name") or "",
                )
            )
        return result

    async def fetch_all(self) -> tuple[Permit, list[Reservation], list[Favorite]]:
        data = await self._post("/login/getbase")
        permit_raw = self._extract_permit(data)
        self._cache_media_defaults(permit_raw)
        return (
            self._map_permit(permit_raw),
            self._map_reservations(permit_raw),
            self._map_favorites(permit_raw),
        )

    async def start_reservation(
        self, license_plate: str, end_time: datetime, name: str | None = None
    ) -> None:
        """Create a reservation starting now."""
        normalized = _normalize_plate(license_plate)
        start_time = datetime.now(UTC)
        payload = {
            "permitMediaTypeID": self._permit_media_type_id,
            "permitMediaCode": self._permit_media_code,
            "DateFrom": _format_ts(start_time),
            "DateUntil": _format_ts(end_time),
            "LicensePlate": {
                "Value": normalized,
                "Name": name or normalized,
            },
        }
        await self._post("/reservation/create", payload)

    async def end_reservation(self, reservation_id: str) -> None:
        """End a reservation immediately."""
        payload = {
            "permitMediaTypeID": self._permit_media_type_id,
            "permitMediaCode": self._permit_media_code,
            "ReservationID": reservation_id,
        }
        await self._post("/reservation/end", payload)

    async def add_favorite(self, license_plate: str, name: str | None = None) -> None:
        normalized = _normalize_plate(license_plate)
        name_value = name or normalized
        payload = {
            "permitMediaTypeID": self._permit_media_type_id,
            "permitMediaCode": self._permit_media_code,
            "licensePlate": {"Value": normalized, "Name": name_value},
            "updateLicensePlate": None,
            "name": name_value,
        }
        await self._post("/permitmedialicenseplate/upsert", payload)

    async def remove_favorite(self, license_plate: str) -> None:
        normalized = _normalize_plate(license_plate)
        payload = {
            "permitMediaTypeID": self._permit_media_type_id,
            "permitMediaCode": self._permit_media_code,
            "licensePlate": normalized,
            "name": normalized,
        }
        await self._post("/permitmedialicenseplate/remove", payload)
