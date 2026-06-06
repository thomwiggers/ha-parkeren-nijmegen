import aiohttp
import pytest

from custom_components.parkeren_nijmegen.api import NijmegenParkingAPI

SAMPLE_PERMIT_DATA = {
    "Name": "",
    "Permits": [
        {
            "Code": None,
            "Type": None,
            "TypeCode": None,
            "ZoneCode": "Z",
            "PermitMedias": [
                {
                    "TypeID": 7,
                    "Code": "CARD-1",
                    "Balance": 120,
                    "RestrictedProlongReservationIDs": [],
                    "ActiveReservations": [
                        {
                            "ReservationID": "123",
                            "ValidFrom": "2024-01-01T09:00:00Z",
                            "ValidUntil": "2024-01-01T10:00:00Z",
                            "LicensePlate": {
                                "Value": "ab-12 cd",
                                "DisplayValue": "AB-12-CD",
                            },
                        }
                    ],
                    "LicensePlates": [
                        {
                            "Value": "xy-99-zz",
                            "Name": "Family",
                            "ValidFrom": "0001-01-01T00:00:00",
                            "ValidUntil": "9999-12-31T23:59:59.9999999",
                        }
                    ],
                    "HasHistory": False,
                    "RemainingUpgrades": 0,
                    "RemainingDowngrades": 0,
                }
            ],
            "UnitFormat": 3,
            "StartTariff": 0,
            "ProlongMinutes": 10,
            "BlockTimes": [
                {
                    "ValidFrom": "2024-01-01T08:00:00Z",
                    "ValidUntil": "2024-01-01T17:00:00Z",
                    "Units": 0,
                    "Seconds": 0,
                    "IsException": False,
                    "IsDefined": False,
                    "IsAllowed": True,
                    "IsFree": True,
                    "DayOfWeek": 0,
                },
                {
                    "ValidFrom": "2024-01-02T08:00:00Z",
                    "ValidUntil": "2024-01-02T17:00:00Z",
                    "Units": 1.0,
                    "Seconds": 60,
                    "IsException": False,
                    "IsDefined": True,
                    "IsAllowed": True,
                    "IsFree": False,
                    "DayOfWeek": 1,
                },
            ],
        }
    ],
    "Configuration": {"ShowPrivacyInfo": False},
}

SAMPLE_LOGIN_RESPONSE = {
    "Name": "",
    "Permits": SAMPLE_PERMIT_DATA["Permits"],
    "Configuration": {"ShowPrivacyInfo": False},
}

SAMPLE_BAD_LOGIN_RESPONSE = {
    "ErrorMessage": "The number or PIN is not correct",
    "LoginStatus": 2,
    "Result": 0,
    "RequiresOtp": False,
}


@pytest.fixture
async def http_session():
    async with aiohttp.ClientSession() as session:
        yield session


@pytest.fixture
async def api_client(http_session):
    api = NijmegenParkingAPI(http_session)
    api._username = "testuser"
    api._password = "testpass"
    api._permit_media_type_id = 7
    api._permit_media_code = "CARD-1"
    yield api
