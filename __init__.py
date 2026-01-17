"""
@file __init__.py
@author Freebox Home Contributors
@brief Home Assistant integration for Freebox devices (Freebox v6 and Freebox mini 4K).
@version 1.2.0

This module provides the main integration setup for Freebox routers, including:
- Configuration entry management
- Service registration (deprecated reboot service)
- Platform forwarding to specialized entity platforms
- YAML configuration support (deprecated)

@section features Features
- Automatic discovery via Zeroconf/mDNS
- Token-based authentication with Freebox router
- Support for multiple Freebox instances
- Periodic updates of device/sensor data
- Home automation capabilities via Freebox Home API

@section modules Related Modules
- @ref open_helper - Non-blocking API connection helper
- @ref router - Router management and data synchronization
- @ref config_flow - Configuration flow handling
"""
from __future__ import annotations

import logging
from datetime import timedelta

import voluptuous as vol
from freebox_api.exceptions import AuthorizationError, HttpRequestError, InvalidTokenError

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import async_track_time_interval, async_track_utc_time_change
from homeassistant.util import dt as dt_util
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    CONF_REBOOT_INTERVAL_DAYS,
    DEFAULT_REBOOT_INTERVAL_DAYS,
    CONF_REBOOT_TIME,
    DOMAIN,
    PLATFORMS,
    SERVICE_REBOOT,
)
from .open_helper import async_open_freebox
from .router import FreeboxConfigEntry, FreeboxRouter, get_api

## @var FREEBOX_SCHEMA
#  Configuration schema for a single Freebox device instance
#  @details Schema requires:
#  - host: Freebox router hostname/IP
#  - port: Freebox router HTTPS port
FREEBOX_SCHEMA = vol.Schema(
    {vol.Required(CONF_HOST): cv.string, vol.Required(CONF_PORT): cv.port}
)

## @var CONFIG_SCHEMA
#  Configuration schema for the Freebox integration (deprecated)
#  @deprecated Use config entries instead of YAML configuration
CONFIG_SCHEMA = vol.Schema(
    vol.All(
        cv.deprecated(DOMAIN),
        {DOMAIN: vol.Schema(vol.All(cv.ensure_list, [FREEBOX_SCHEMA]))},
    ),
    extra=vol.ALLOW_EXTRA,
)

## @var _LOGGER
#  Logger instance for module-level logging
_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """
    @brief Set up the Freebox integration from YAML configuration.
    
    @details
    This is the legacy YAML configuration setup method. It imports YAML config
    entries and converts them to config entry format for use with the modern
    Home Assistant configuration entry system.
    
    @param[in] hass The Home Assistant instance
    @param[in] config The configuration dictionary from configuration.yaml
    @return True if setup was successful, False otherwise
    @see async_setup_entry For the modern config entry setup method
    @deprecated Use configuration entries instead of YAML configuration
    """
    if DOMAIN in config:
        for entry_config in config[DOMAIN]:
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN, context={"source": SOURCE_IMPORT}, data=entry_config
                )
            )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: FreeboxConfigEntry) -> bool:
    """
    @brief Set up Freebox integration from a config entry.
    
    @details
    This function performs the following steps:
    1. Gets or creates a Freepybox API instance with proper token file storage
    2. Opens the connection without blocking the event loop (executor-based)
    3. Validates that all API sub-modules were initialized
    4. Fetches initial Freebox system configuration
    5. Creates a FreeboxRouter instance for data management
    6. Performs initial data update
    7. Sets up periodic update polling
    8. Forwards setup to specialized entity platforms
    9. Registers deprecated reboot service
    10. Registers shutdown handler
    
    @param[in] hass The Home Assistant instance
    @param[in] entry The config entry containing Freebox connection details
    @return True if setup was successful
    @throw ConfigEntryNotReady If connection fails or setup cannot be completed
    @see async_unload_entry For the cleanup function
    @see open_helper.async_open_freebox For non-blocking connection details
    """
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]
    
    _LOGGER.debug("Setting up Freebox integration for %s:%d", host, port)
    api = await get_api(hass, host)

    try:
        await async_open_freebox(hass, api, host, port)
    except (HttpRequestError, AuthorizationError, InvalidTokenError) as err:
        _LOGGER.error("Failed to connect to Freebox at %s:%d: %s", host, port, err)
        raise ConfigEntryNotReady from err

    # Defensive: ensure Freepybox initialized its sub-APIs (system, connection, etc.).
    # If missing, treat as not ready so HA retries instead of crashing.
    if not hasattr(api, "system"):
        _LOGGER.warning("Freebox API not fully initialized; retrying setup later")
        raise ConfigEntryNotReady

    try:
        freebox_config = await api.system.get_config()
    except HttpRequestError as err:
        _LOGGER.error("Failed to get Freebox system config: %s", err)
        raise ConfigEntryNotReady from err

    router = FreeboxRouter(hass, entry, api, freebox_config)
    _LOGGER.info(
        "Freebox router initialized: %s (%s) at %s:%d",
        router.name,
        router.model_id,
        host,
        port,
    )
    
    # Get scan interval from options or use default
    scan_interval_seconds = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    scan_interval = timedelta(seconds=scan_interval_seconds)
    _LOGGER.debug("Using scan interval: %d seconds", scan_interval_seconds)
    
    await router.update_all()
    entry.async_on_unload(
        async_track_time_interval(hass, router.update_all, scan_interval)
    )

    # Scheduled reboot if enabled
    reboot_interval_days = entry.options.get(
        CONF_REBOOT_INTERVAL_DAYS, DEFAULT_REBOOT_INTERVAL_DAYS
    )
    reboot_time_str = entry.options.get(CONF_REBOOT_TIME, "03:00")

    if reboot_interval_days and reboot_interval_days > 0:
        hour, minute = 3, 0
        try:
            hour_str, minute_str = reboot_time_str.split(":", maxsplit=1)
            hour = int(hour_str)
            minute = int(minute_str)
        except (ValueError, AttributeError):
            _LOGGER.warning("Invalid reboot_time '%s', falling back to 03:00", reboot_time_str)
            hour, minute = 3, 0

        async def _scheduled_reboot(_now):
            _LOGGER.info(
                "Scheduled reboot triggered (every %d days at %02d:%02d) for %s",
                reboot_interval_days,
                hour,
                minute,
                host,
            )
            await router.reboot()

        # Align to local time daily, but execute every N days by tracking last run
        last_run = dt_util.now()

        async def _reboot_if_due(now):
            nonlocal last_run
            # Run only if at least N days elapsed
            if (now - last_run) < timedelta(days=reboot_interval_days):
                return
            await _scheduled_reboot(now)
            last_run = now

        entry.async_on_unload(
            async_track_utc_time_change(
                hass,
                _reboot_if_due,
                hour=hour,
                minute=minute,
                second=0,
            )
        )

    entry.runtime_data = router

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Services
    async def async_reboot(call: ServiceCall) -> None:
        """
        @brief Handle reboot service call (deprecated).
        
        @details
        The Freebox reboot service has been replaced by a dedicated button entity
        and marked as deprecated. This handler logs a warning and delegates to
        the router's reboot method.
        
        @param[in] call The service call data
        @return None
        @see FreeboxRouter.reboot For the underlying reboot implementation
        """
        # The Freebox reboot service has been replaced by a
        # dedicated button entity and marked as deprecated
        _LOGGER.warning(
            "The 'freebox.reboot' service is deprecated and "
            "replaced by a dedicated reboot button entity; please "
            "use that entity to reboot the freebox instead"
        )
        await router.reboot()

    hass.services.async_register(DOMAIN, SERVICE_REBOOT, async_reboot)

    async def async_close_connection(event: Event) -> None:
        """
        @brief Close Freebox connection on Home Assistant stop event.
        
        @details
        This handler is called when Home Assistant is shutting down. It ensures
        the Freebox API connection is properly closed and cleaned up.
        
        @param[in] event The Home Assistant stop event
        @return None
        @see FreeboxRouter.close For connection cleanup implementation
        """
        _LOGGER.debug("Closing Freebox connection for %s", host)
        await router.close()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, async_close_connection)
    )

    # Register listener to reload on options update
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True

async def async_reload_entry(hass: HomeAssistant, entry: FreeboxConfigEntry) -> None:
    """
    @brief Reload the config entry when options change.
    
    @details
    This function is called when the user updates integration options (such as
    scan interval). It triggers a full reload of the integration to apply the
    new settings.
    
    @param[in] hass The Home Assistant instance
    @param[in] entry The config entry with updated options
    @return None
    """
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: FreeboxConfigEntry) -> bool:
    """
    @brief Unload a Freebox config entry.
    
    @details
    This function is called when a config entry is being removed or when the
    integration is being disabled. It performs cleanup operations:
    1. Unloads all platform-specific entities
    2. Closes the API connection
    3. Removes the deprecated reboot service
    
    @param[in] hass The Home Assistant instance
    @param[in] entry The config entry to unload
    @return True if unload was successful, False otherwise
    @see async_setup_entry For the corresponding setup function
    """
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        # Close API connection and remove deprecated reboot service
        await entry.runtime_data.close()
        hass.services.async_remove(DOMAIN, SERVICE_REBOOT)

    return unload_ok
