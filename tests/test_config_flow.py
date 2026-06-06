from unittest.mock import AsyncMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType

from custom_components.parkeren_nijmegen.const import (
    CONF_PASSWORD,
    CONF_USERNAME,
    DOMAIN,
)


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    return


async def test_config_flow_shows_user_form(hass):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_config_flow_success(hass):
    with patch(
        "custom_components.parkeren_nijmegen.config_flow.NijmegenParkingAPI"
    ) as MockAPI:
        instance = MockAPI.return_value
        instance.login = AsyncMock()
        instance._permit_media_code = "CARD-1"
        instance._permit_media_type_id = 7

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: "334412", CONF_PASSWORD: "8563"},
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_USERNAME] == "334412"
    assert result["data"][CONF_PASSWORD] == "8563"
    assert result["data"]["permit_media_code"] == "CARD-1"
    assert result["data"]["permit_media_type_id"] == 7


async def test_config_flow_invalid_auth(hass):
    from custom_components.parkeren_nijmegen.exceptions import AuthError

    with patch(
        "custom_components.parkeren_nijmegen.config_flow.NijmegenParkingAPI"
    ) as MockAPI:
        instance = MockAPI.return_value
        instance.login = AsyncMock(side_effect=AuthError("bad creds"))

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: "334412", CONF_PASSWORD: "wrong"},
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_config_flow_cannot_connect(hass):

    from custom_components.parkeren_nijmegen.exceptions import ProviderError

    with patch(
        "custom_components.parkeren_nijmegen.config_flow.NijmegenParkingAPI"
    ) as MockAPI:
        instance = MockAPI.return_value
        instance.login = AsyncMock(side_effect=ProviderError("timeout"))

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: "334412", CONF_PASSWORD: "8563"},
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_config_flow_duplicate_aborts(hass):
    with patch(
        "custom_components.parkeren_nijmegen.config_flow.NijmegenParkingAPI"
    ) as MockAPI:
        instance = MockAPI.return_value
        instance.login = AsyncMock()
        instance._permit_media_code = "CARD-1"
        instance._permit_media_type_id = 7

        # First entry
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_USERNAME: "334412", CONF_PASSWORD: "8563"}
        )

    with patch(
        "custom_components.parkeren_nijmegen.config_flow.NijmegenParkingAPI"
    ) as MockAPI:
        instance = MockAPI.return_value
        instance.login = AsyncMock()
        instance._permit_media_code = "CARD-1"
        instance._permit_media_type_id = 7

        # Duplicate entry
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_USERNAME: "334412", CONF_PASSWORD: "8563"}
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"
