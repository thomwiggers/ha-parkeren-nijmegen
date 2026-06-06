from __future__ import annotations

import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import aiohttp_client

from .api import NijmegenParkingAPI
from .const import (
    CONF_PASSWORD,
    CONF_PERMIT_MEDIA_CODE,
    CONF_PERMIT_MEDIA_TYPE_ID,
    CONF_USERNAME,
    DOMAIN,
)
from .exceptions import AuthError, ProviderError

_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class NijmegenConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                permit_media_code, permit_media_type_id = (
                    await self._validate_credentials(
                        user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
                    )
                )
            except AuthError:
                errors["base"] = "invalid_auth"
            except (ProviderError, aiohttp.ClientError):
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(f"nijmegen_{permit_media_code}")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"Nijmegen ({permit_media_code})",
                    data={
                        CONF_USERNAME: user_input[CONF_USERNAME],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                        CONF_PERMIT_MEDIA_CODE: permit_media_code,
                        CONF_PERMIT_MEDIA_TYPE_ID: permit_media_type_id,
                    },
                )

        return self.async_show_form(
            step_id="user", data_schema=_USER_SCHEMA, errors=errors
        )

    async def async_step_reauth(self, entry_data):
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        errors = {}
        if user_input is not None:
            entry = self._get_reauth_entry()
            try:
                await self._validate_credentials(
                    user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
                )
            except AuthError:
                errors["base"] = "invalid_auth"
            except (ProviderError, aiohttp.ClientError):
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={
                        CONF_USERNAME: user_input[CONF_USERNAME],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                    },
                )
        return self.async_show_form(
            step_id="reauth_confirm", data_schema=_USER_SCHEMA, errors=errors
        )

    async def _validate_credentials(
        self, username: str, password: str
    ) -> tuple[str, int]:
        session = aiohttp_client.async_get_clientsession(self.hass)
        api = NijmegenParkingAPI(session)
        await api.login(username, password)
        return api._permit_media_code or username, api._permit_media_type_id
