"""
@file config_flow.py
@brief Config flow to configure the Freebox integration.

This module handles the configuration flow for setting up the Freebox integration
in Home Assistant, including device discovery, authentication, and permission
verification.
"""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from freebox_api.exceptions import (
    AuthorizationError,
    HttpRequestError,
    InvalidTokenError,
)

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import DOMAIN, FreeboxHomeCategory
from .open_helper import async_open_freebox
from .router import get_api, get_hosts_list_if_supported

_LOGGER = logging.getLogger(__name__)  ##< Logger instance for this module


class FreeboxFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Freebox integration.
    
    This class manages the configuration flow for the Freebox integration,
    including user input, device linking, permission verification, and
    automatic discovery via Zeroconf.
    """

    VERSION = 1  ##< Configuration entry version

    def __init__(self) -> None:
        """Initialize Freebox config flow.
        
        Sets up the initial state with host and port as None.
        """
        self._host: str | None = None  ##< Freebox router host address
        self._port: int | None = None  ##< Freebox router port number

    def _show_setup_form(
        self,
        user_input: dict[str, Any] | None = None,
        errors: dict[str, str] | None = None,
    ) -> ConfigFlowResult:
        """Show the setup form to the user.
        
        @param user_input Optional dictionary containing user input data (host and port).
        @param errors Optional dictionary containing validation errors to display.
        @return ConfigFlowResult with the setup form.
        """

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

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user.
        
        This is the entry point for user-initiated configuration. It validates
        the provided host and port, checks for duplicate configurations, and
        proceeds to the linking step.
        
        @param user_input Optional dictionary containing CONF_HOST and CONF_PORT.
        @return ConfigFlowResult either showing the form or proceeding to link step.
        """
        errors: dict[str, str] = {}

        if user_input is None:
            return self._show_setup_form(user_input, errors)

        self._host = user_input[CONF_HOST]
        self._port = user_input[CONF_PORT]

        # Check if already configured
        await self.async_set_unique_id(self._host)
        self._abort_if_unique_id_configured()

        return await self.async_step_link()

    async def async_step_link(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Attempt to link with the Freebox router.

        Given a configured host, will ask the user to press the button
        to connect to the router. This step handles authentication and
        verifies basic connectivity and permissions.
        
        @param user_input Optional dictionary, triggers linking attempt if present.
        @return ConfigFlowResult showing link form, error form, or proceeding to next step.
        """
        if user_input is None:
            return self.async_show_form(step_id="link")

        errors: dict[str, str] = {}

        try:
            # Get our handle to deal
            fbx = await get_api(self.hass, self._host)
            _LOGGER.info(fbx)

            # Open connection and check authentication
            await async_open_freebox(self.hass, fbx, self._host, self._port)

            # Check permissions
            freebox_config = await fbx.system.get_config()
            await get_hosts_list_if_supported(fbx)
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

        except Exception as err:  # pylint: disable=broad-except
            _LOGGER.exception(
                "Unknown error connecting with Freebox router at %s", self._host
            )
            errors["base"] = "unknown"

        return self.async_show_form(step_id="link", errors=errors)

    async def async_step_permissions(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Attempt to get Home permissions with the Freebox router.
        
        Verifies that the integration has the necessary permissions for home
        automation features, including home, camera, and settings access.
        
        @param user_input Optional dictionary, triggers permission check if present.
        @return ConfigFlowResult showing permission form with errors or creating entry.
        """
        errors: dict[str, str] = {}

        try:
            # Get our handle to deal
            fbx = await get_api(self.hass, self._host)
            _LOGGER.info(fbx)

            # Open connection and check authentication
            await async_open_freebox(self.hass, fbx, self._host, self._port)

            # Check permissions
            freebox_permissions = await fbx.get_permissions()
            if freebox_permissions["home"] is False:
                await fbx.close()
                errors["base"] = "home_permission"
                return self.async_show_form(step_id="permissions", errors=errors)

            if freebox_permissions[FreeboxHomeCategory.CAMERA] is False:
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

        except Exception as err:  # pylint: disable=broad-except
            _LOGGER.exception(
                "Unknown error connecting with Freebox router at %s", self._host
            )
            errors["base"] = "unknown"

        return self.async_show_form(step_id="permissions", errors=errors)

    async def async_step_import(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Import a config entry.
        
        Allows importing configuration from YAML or other sources by
        delegating to the user step.
        
        @param user_input Optional dictionary containing configuration to import.
        @return ConfigFlowResult from the user step.
        """
        return await self.async_step_user(user_input)

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """
        @brief Initialize flow from zeroconf.
        
        Handles automatic discovery of Freebox routers on the network via
        Zeroconf/mDNS and extracts connection information to start the
        configuration flow.
        
        @param discovery_info ZeroconfServiceInfo containing discovered device information.
        @return ConfigFlowResult from the user step with auto-filled host and port.
        """
        zeroconf_properties = discovery_info.properties
        host = zeroconf_properties["api_domain"]
        port = zeroconf_properties["https_port"]
        return await self.async_step_user({CONF_HOST: host, CONF_PORT: port})