import aiohttp
import pytest
from custom_components.parkeren_nijmegen.api import NijmegenParkingAPI

SAMPLE_PERMIT_DATA = {
    "Permit": {
        "ZoneCode": "ZONE-1",
        "BlockTimes": [
            {
                "IsFree": True,
                "ValidFrom": "2024-01-01T09:00:00+01:00",
                "ValidUntil": "2024-01-01T18:00:00+01:00",
            },
            {
                "IsFree": False,
                "ValidFrom": "2024-01-02T09:00:00+01:00",
                "ValidUntil": "2024-01-02T18:00:00+01:00",
            },
        ],
        "PermitMedias": [
            {
                "TypeID": 1,
                "Code": "CARD-1",
                "Balance": "120",
                "ActiveReservations": [
                    {
                        "ReservationID": "123",
                        "ValidFrom": "2024-01-01T10:00:00+01:00",
                        "ValidUntil": "2024-01-01T11:00:00+01:00",
                        "LicensePlate": {
                            "Value": "ab-12 cd",
                            "DisplayValue": "AB-12-CD",
                        },
                    }
                ],
                "LicensePlates": [{"Value": "xy-99-zz", "Name": "Family"}],
            }
        ],
    }
}

SAMPLE_LOGIN_RESPONSE = {
    "LoginStatus": 0,
    "Token": "test-token-abc",
    "ErrorMessage": None,
    **SAMPLE_PERMIT_DATA,
}


@pytest.fixture
async def http_session():
    async with aiohttp.ClientSession() as session:
        yield session


@pytest.fixture
async def api_client(http_session):
    api = NijmegenParkingAPI(http_session)
    api._token = "pre-set-token"
    api._username = "testuser"
    api._password = "testpass"
    api._permit_media_type_id = 1
    api._permit_media_code = "CARD-1"
    yield api
