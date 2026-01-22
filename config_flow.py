""""""
from __future__ import annotations

import logging
import re
from typing import Any

import voluptuous as vol
from freebox_api.exceptions import (
    AuthorizationError,
    HttpRequestError,
    InvalidTokenError,
)

from homeassistant.config_entries import ConfigFlow, OptionsFlow
from homeassistant.data_entry_flow import FlowResult
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import callback
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import (
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    CONF_REBOOT_INTERVAL_DAYS,
    DEFAULT_REBOOT_INTERVAL_DAYS,
    CONF_REBOOT_TIME,
    CONF_TEMP_REFRESH_INTERVAL,
    DEFAULT_TEMP_REFRESH_INTERVAL,
    CONF_TEMP_REFRESH_DURATION,
    DEFAULT_TEMP_REFRESH_DURATION,
    DOMAIN,
    FreeboxHomeCategory,
)
from .open_helper import async_open_freebox
from .router import get_api, get_hosts_list_if_supported
from .validation import (
    validate_port,
    validate_scan_interval,
    validate_reboot_interval,
    validate_reboot_time,
    validate_temp_refresh_interval,
    validate_temp_refresh_duration,
)

_LOGGER = logging.getLogger(__name__)  ##< Logger instance for this module


class FreeboxFlowHandler(ConfigFlow, domain=DOMAIN):
    """ Handle the configuration flow for the Freebox integration.

    Manages user-initiated setup, authentication, permission checks, and
    Zeroconf discovery for Freebox routers.
    """

    VERSION = 1  ##< Configuration entry version

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """ Get the options flow for this handler.
        Args:
            config_entry: The config entry to configure options for
        Returns:
            FreeboxOptionsFlowHandler instance
        """
        return FreeboxOptionsFlowHandler(config_entry)

    def __init__(self) -> None:
        """ Initialize Freebox config flow.

        Sets up the initial state with host and port as None.
        Returns:
            None
        """
        self._host: str | None = None  ##< Freebox router host address
        self._port: int | None = None  ##< Freebox router port number

    def _show_setup_form(
        self,
        user_input: dict[str, Any] | None = None,
        errors: dict[str, str] | None = None,
    ) -> FlowResult:
        """ Show the setup form to the user with input validation.
        Args:
            user_input: Optional dictionary containing provisional host and port
        Args:
            errors: Optional dictionary containing validation errors to display
        Returns:
            ConfigFlowResult rendering the setup form with validators
        """

        if user_input is None:
            user_input = {}

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=user_input.get(CONF_HOST, "")): str,
                    vol.Required(CONF_PORT, default=user_input.get(CONF_PORT, 443)): validate_port,
                }
            ),
            errors=errors or {},
            description_placeholders={
                "port_hint": "Default: 443"
            }
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """ Handle a flow initiated by the user.

        Validates host/port input, ensures the router is not already configured,
        and transitions to the link step to request device authorization.
        Args:
            user_input: Optional dictionary containing CONF_HOST and CONF_PORT
        Returns:
            ConfigFlowResult containing either a form or next step transition
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
        """ Attempt to link with the Freebox router.

        Requests the user to press the router button, establishes a connection,
        performs authentication, and validates basic permissions before proceeding.
        Args:
            user_input: Optional dictionary, triggers linking attempt when provided
        Returns:
            ConfigFlowResult showing link form, error form, or proceeding to next step
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
    ) -> FlowResult:
        """ Attempt to get Home permissions with the Freebox router.

        Verifies integration permissions for home automation features including
        home, camera, and settings access before finalizing configuration.
        Args:
            user_input: Optional dictionary, triggers permission check when provided
        Returns:
            ConfigFlowResult showing permission form with errors or creating entry
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

            if freebox_permissions[FreeboxHomeCategory.CAMERA.value] is False:
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
    ) -> FlowResult:
        """ Import a config entry.

        Allows importing configuration from YAML or other sources by
        delegating to the user step.
        Args:
            user_input: Optional dictionary containing configuration to import
        Returns:
            ConfigFlowResult produced by the user step
        """
        return await self.async_step_user(user_input)

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> FlowResult:
        """ Initialize flow from Zeroconf discovery.

        Handles automatic discovery of Freebox routers on the network via
        Zeroconf/mDNS and extracts connection information to start the
        configuration flow.
        Args:
            discovery_info: ZeroconfServiceInfo containing discovered device information
        Returns:
            ConfigFlowResult from the user step with auto-filled host and port
        """
        zeroconf_properties = discovery_info.properties
        host = zeroconf_properties["api_domain"]
        port = zeroconf_properties["https_port"]
        return await self.async_step_user({CONF_HOST: host, CONF_PORT: port})


class FreeboxOptionsFlowHandler(OptionsFlow):
        """ Handle options flow for Freebox integration.
    
        Allows users to configure integration parameters such as scan interval
        after initial setup.
        """

        def __init__(self, config_entry):
            """ Initialize the options flow handler.
        Args:
            config_entry: The config entry being configured
        Returns:
            None
            """
            self._config_entry = config_entry

        async def async_step_init(self, user_input=None):
            """ Manage the options for the Freebox integration.
        Args:
            user_input: Optional dictionary containing user configuration
        Returns:
            ConfigFlowResult showing form or creating entry with updated options
            """
            if user_input is not None:
                return self.async_create_entry(title="", data=user_input)

            return self.async_show_form(
                step_id="init",
                data_schema=vol.Schema(
                    {
                        vol.Optional(
                            CONF_SCAN_INTERVAL,
                            default=self._config_entry.options.get(
                                CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                            ),
                        ): validate_scan_interval,

                        vol.Optional(
                            CONF_REBOOT_INTERVAL_DAYS,
                            default=self._config_entry.options.get(
                                CONF_REBOOT_INTERVAL_DAYS, DEFAULT_REBOOT_INTERVAL_DAYS
                            ),
                        ): validate_reboot_interval,
                        
                        vol.Optional(
                            CONF_REBOOT_TIME,
                            default=self._config_entry.options.get(
                                CONF_REBOOT_TIME, "03:00"
                            ),
                        ): validate_reboot_time,
                        
                        vol.Optional(
                            CONF_TEMP_REFRESH_INTERVAL,
                            default=self._config_entry.options.get(
                                CONF_TEMP_REFRESH_INTERVAL, DEFAULT_TEMP_REFRESH_INTERVAL
                            ),
                        ): validate_temp_refresh_interval,
                        
                        vol.Optional(
                            CONF_TEMP_REFRESH_DURATION,
                            default=self._config_entry.options.get(
                                CONF_TEMP_REFRESH_DURATION, DEFAULT_TEMP_REFRESH_DURATION
                            ),
                        ): validate_temp_refresh_duration,
                    }
                ),
            )
