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
    """
    @brief Handle the configuration flow for the Freebox integration.

    Manages user-initiated setup, authentication, permission checks, and
    Zeroconf discovery for Freebox routers.
    """

    VERSION = 1  ##< Configuration entry version

    def __init__(self) -> None:
        """
        @brief Initialize Freebox config flow.

        Sets up the initial state with host and port as None.

        @return None
        """
        self._host: str | None = None  ##< Freebox router host address
        self._port: int | None = None  ##< Freebox router port number

    def _show_setup_form(
        self,
        user_input: dict[str, Any] | None = None,
        errors: dict[str, str] | None = None,
    ) -> ConfigFlowResult:
        """
        @brief Show the setup form to the user.

        @param[in] user_input Optional dictionary containing provisional host and port
        @param[in] errors Optional dictionary containing validation errors to display
        @return ConfigFlowResult rendering the setup form
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
        """
        @brief Handle a flow initiated by the user.

        Validates host/port input, ensures the router is not already configured,
        and transitions to the link step to request device authorization.

        @param[in] user_input Optional dictionary containing CONF_HOST and CONF_PORT
        @return ConfigFlowResult containing either a form or next step transition
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
        """
        @brief Attempt to link with the Freebox router.

        Requests the user to press the router button, establishes a connection,
        performs authentication, and validates basic permissions before proceeding.

        @param[in] user_input Optional dictionary, triggers linking attempt when provided
        @return ConfigFlowResult showing link form, error form, or proceeding to next step
        """
        if user_input is None:
            return self.async_show_form(step_id="link")

        errors: dict[str, str] = {}

        fbx = None
        try:
            # Get our handle to deal
            fbx = await get_api(self.hass, self._host)
            _LOGGER.info("Attempting to connect to Freebox at %s:%d", self._host, self._port)

            # Open connection and check authentication
            await async_open_freebox(self.hass, fbx, self._host, self._port)

            # Check permissions
            freebox_config = await fbx.system.get_config()
            await get_hosts_list_if_supported(fbx)
            await self.hass.async_block_till_done()

            if freebox_config["model_info"]["has_home_automation"] is True:
                return await self.async_step_permissions()

            return self.async_create_entry(
                title=self._host,
                data={CONF_HOST: self._host, CONF_PORT: self._port},
            )
        except InvalidTokenError as error:
            _LOGGER.error("Invalid token for Freebox at %s: %s", self._host, error)
            errors["base"] = "invalid_token"

        except AuthorizationError as error:
            _LOGGER.error("Authorization failed for Freebox at %s: %s", self._host, error)
            errors["base"] = "register_failed"

        except HttpRequestError as error:
            _LOGGER.error("Connection error to Freebox at %s: %s", self._host, error)
            errors["base"] = "cannot_connect"

        except Exception as err:  # pylint: disable=broad-except
            _LOGGER.exception(
                "Unexpected error connecting to Freebox at %s: %s", self._host, err
            )
            errors["base"] = "unknown"

        finally:
            if fbx is not None:
                await fbx.close()

        return self.async_show_form(step_id="link", errors=errors)

    async def async_step_permissions(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """
        @brief Attempt to get Home permissions with the Freebox router.

        Verifies integration permissions for home automation features including
        home, camera, and settings access before finalizing configuration.

        @param[in] user_input Optional dictionary, triggers permission check when provided
        @return ConfigFlowResult showing permission form with errors or creating entry
        """
        errors: dict[str, str] = {}

        fbx = None
        try:
            # Get our handle to deal
            fbx = await get_api(self.hass, self._host)
            _LOGGER.info("Checking permissions for Freebox at %s:%d", self._host, self._port)

            # Open connection and check authentication
            await async_open_freebox(self.hass, fbx, self._host, self._port)

            # Check permissions
            freebox_permissions = await fbx.get_permissions()
            if freebox_permissions["home"] is False:
                _LOGGER.warning("Freebox at %s: home permission not granted", self._host)
                errors["base"] = "home_permission"
                return self.async_show_form(step_id="permissions", errors=errors)

            if freebox_permissions[FreeboxHomeCategory.CAMERA] is False:
                _LOGGER.warning("Freebox at %s: camera permission not granted", self._host)
                errors["base"] = "camera_permission"
                return self.async_show_form(step_id="permissions", errors=errors)

            if freebox_permissions["settings"] is False:
                _LOGGER.warning("Freebox at %s: settings permission not granted", self._host)
                errors["base"] = "settings_permission"
                return self.async_show_form(step_id="permissions", errors=errors)

            _LOGGER.info("All required permissions granted for Freebox at %s", self._host)
            return self.async_create_entry(
                title=self._host,
                data={CONF_HOST: self._host, CONF_PORT: self._port},
            )
        except InvalidTokenError as error:
            _LOGGER.error("Invalid token for Freebox at %s: %s", self._host, error)
            errors["base"] = "invalid_token"

        except AuthorizationError as error:
            _LOGGER.error("Authorization failed for Freebox at %s: %s", self._host, error)
            errors["base"] = "register_failed"

        except HttpRequestError as error:
            _LOGGER.error("Connection error to Freebox at %s: %s", self._host, error)
            errors["base"] = "cannot_connect"

        except Exception as err:  # pylint: disable=broad-except
            _LOGGER.exception(
                "Unexpected error checking permissions for Freebox at %s: %s", self._host, err
            )
            errors["base"] = "unknown"

        finally:
            if fbx is not None:
                await fbx.close()

        return self.async_show_form(step_id="permissions", errors=errors)

    async def async_step_import(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """
        @brief Import a config entry.

        Allows importing configuration from YAML or other sources by
        delegating to the user step.

        @param[in] user_input Optional dictionary containing configuration to import
        @return ConfigFlowResult produced by the user step
        """
        return await self.async_step_user(user_input)

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """
        @brief Initialize flow from Zeroconf discovery.

        Handles automatic discovery of Freebox routers on the network via
        Zeroconf/mDNS and extracts connection information to start the
        configuration flow.

        @param[in] discovery_info ZeroconfServiceInfo containing discovered device information
        @return ConfigFlowResult from the user step with auto-filled host and port
        """
        zeroconf_properties = discovery_info.properties
        host = zeroconf_properties["api_domain"]
        port = zeroconf_properties["https_port"]
        return await self.async_step_user({CONF_HOST: host, CONF_PORT: port})