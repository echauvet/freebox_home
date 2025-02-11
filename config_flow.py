"""Config flow to configure the Freebox integration."""
import logging

from freebox_api.exceptions import (
    AuthorizationError,
    HttpRequestError,
    InvalidTokenError,
)
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import DOMAIN
from .router import get_api

_LOGGER = logging.getLogger(__name__)


class FreeboxFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1

    def __init__(self):
        """Initialize Freebox config flow."""
        self._host = None
        self._port = None

    def _show_setup_form(self, user_input=None, errors=None):
        """Show the setup form to the user."""

        if user_input is None:
            user_input = {}

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=user_input.get(CONF_HOST, "")): str,
                    vol.Required(CONF_PORT, default=user_input.get(CONF_PORT, "")): int,
                }
            ),
            errors=errors or {},
        )

    async def async_step_user(self, user_input=None):
        """Handle a flow initiated by the user."""
        errors = {}

        if user_input is None:
            return self._show_setup_form(user_input, errors)

        self._host = user_input[CONF_HOST]
        self._port = user_input[CONF_PORT]

        # Check if already configured
        await self.async_set_unique_id(self._host)
        self._abort_if_unique_id_configured()

        return await self.async_step_link()

    async def async_step_link(self, user_input=None):
        """Attempt to link with the Freebox router.

        Given a configured host, will ask the user to press the button
        to connect to the router.
        """
        if user_input is None:
            return self.async_show_form(step_id="link")

        errors = {}

        try:
            # Get our handle to deal
            fbx = await get_api(self.hass, self._host)
            _LOGGER.info(fbx)

            # Open connection and check authentication
            await fbx.open(self._host, self._port)

            # Check permissions
            freebox_config = await fbx.system.get_config()
            await fbx.lan.get_hosts_list()
            await self.hass.async_block_till_done()

            # Close connection
            await fbx.close()

            if freebox_config["model_info"]["has_home_automation"] is True:
                return await self.async_step_permissions()

            return self.async_create_entry(
                title=self._host,
                data={CONF_HOST: self._host, CONF_PORT: self._port},
            )

        except InvalidTokenError as error:
            _LOGGER.error(error)
            errors["base"] = "invalid_token"

        except AuthorizationError as error:
            _LOGGER.error(error)
            errors["base"] = "register_failed"

        except HttpRequestError:
            _LOGGER.error("Error connecting to the Freebox router at %s", self._host)
            errors["base"] = "cannot_connect"

        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception(
                "Unknown error connecting with Freebox router at %s", self._host
            )
            errors["base"] = "unknown"

        return self.async_show_form(step_id="link", errors=errors)

    async def async_step_permissions(self, user_input=None):
        """Attempt to get Home permissions with the Freebox router."""
        errors = {}

        try:
            # Get our handle to deal
            fbx = await get_api(self.hass, self._host)
            _LOGGER.info(fbx)

            # Open connection and check authentication
            await fbx.open(self._host, self._port)

            # Check permissions
            freebox_permissions = await fbx.get_permissions()
            if freebox_permissions["home"] is False:
                await fbx.close()
                errors["base"] = "home_permission"
                return self.async_show_form(step_id="permissions", errors=errors)

            if freebox_permissions["camera"] is False:
                await fbx.close()
                errors["base"] = "camera_permission"
                return self.async_show_form(step_id="permissions", errors=errors)

            if freebox_permissions["settings"] is False:
                await fbx.close()
                errors["base"] = "settings_permission"
                return self.async_show_form(step_id="permissions", errors=errors)

            # Close connection
            await fbx.close()

            return self.async_create_entry(
                title=self._host,
                data={CONF_HOST: self._host, CONF_PORT: self._port},
            )

        except InvalidTokenError as error:
            _LOGGER.error(error)
            errors["base"] = "invalid_token"

        except AuthorizationError as error:
            _LOGGER.error(error)
            errors["base"] = "register_failed"

        except HttpRequestError:
            _LOGGER.error("Error connecting to the Freebox router at %s", self._host)
            errors["base"] = "cannot_connect"

        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception(
                "Unknown error connecting with Freebox router at %s", self._host
            )
            errors["base"] = "unknown"

        return self.async_show_form(step_id="permissions", errors=errors)

    async def async_step_import(self, user_input=None):
        """Import a config entry."""
        return await self.async_step_user(user_input)

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Initialize flow from zeroconf."""
        zeroconf_properties = discovery_info.properties
        host = zeroconf_properties["api_domain"]
        port = zeroconf_properties["https_port"]
        return await self.async_step_user({CONF_HOST: host, CONF_PORT: port})