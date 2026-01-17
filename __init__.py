"""
@file __init__.py
@brief Home Assistant integration for Freebox devices (Freebox v6 and Freebox mini 4K).

This module provides the main integration setup for Freebox routers, including
configuration entry management, service registration, and platform forwarding.
"""
from __future__ import annotations

import asyncio
import logging
import ssl
from datetime import timedelta
from os import path
from typing import Any

import voluptuous as vol
from aiohttp import ClientSession, TCPConnector
import freebox_api.aiofreepybox as aiofreepybox
from freebox_api.aiofreepybox import (
    Access,
    Airmedia,
    Call,
    Connection,
    Freepybox,
    Dhcp,
    Download,
    Freeplug,
    Fs,
    Ftp,
    Fw,
    Home,
    Lan,
    Lcd,
    Netshare,
    Notifications,
    Parental,
    Phone,
    Player,
    Remote,
    Rrd,
    Storage,
    Switch,
    System,
    Tv,
    Upnpav,
    Upnpigd,
    Wifi,
)
from freebox_api.exceptions import AuthorizationError, HttpRequestError, InvalidTokenError

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, PLATFORMS, SERVICE_REBOOT
from .open_helper import async_open_freebox
from .router import FreeboxConfigEntry, FreeboxRouter, get_api

FREEBOX_SCHEMA = vol.Schema(  ##< Configuration schema for a single Freebox device
    {vol.Required(CONF_HOST): cv.string, vol.Required(CONF_PORT): cv.port}
)

CONFIG_SCHEMA = vol.Schema(  ##< Configuration schema for the Freebox integration (deprecated)
    vol.All(
        cv.deprecated(DOMAIN),
        {DOMAIN: vol.Schema(vol.All(cv.ensure_list, [FREEBOX_SCHEMA]))},
    ),
    extra=vol.ALLOW_EXTRA,
)

SCAN_INTERVAL = timedelta(seconds=30)  ##< Update interval for polling Freebox router data

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """
    @brief Set up the Freebox integration from YAML configuration.
    
    @param hass The Home Assistant instance
    @param config The configuration dictionary
    @return True if setup was successful
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
    
    @param hass The Home Assistant instance
    @param entry The config entry containing Freebox connection details
    @return True if setup was successful
    """
    api = await get_api(hass, entry.data[CONF_HOST])

    try:
        await async_open_freebox(
            hass, api, entry.data[CONF_HOST], entry.data[CONF_PORT]
        )
    except (HttpRequestError, AuthorizationError, InvalidTokenError) as err:
        raise ConfigEntryNotReady from err

    # Defensive: ensure Freepybox initialized its sub-APIs (system, connection, etc.).
    # If missing, treat as not ready so HA retries instead of crashing.
    if not hasattr(api, "system"):
        _LOGGER.warning("Freebox API not fully initialized; retrying setup later")
        raise ConfigEntryNotReady

    freebox_config = await api.system.get_config()

    router = FreeboxRouter(hass, entry, api, freebox_config)
    await router.update_all()
    entry.async_on_unload(
        async_track_time_interval(hass, router.update_all, SCAN_INTERVAL)
    )

    entry.runtime_data = router

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Services
    async def async_reboot(call: ServiceCall) -> None:
        """
        @brief Handle reboot service call (deprecated).
        
        @param call The service call data
        @return None
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
        
        @param event The Home Assistant stop event
        @return None
        """
        await router.close()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, async_close_connection)
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: FreeboxConfigEntry) -> bool:
    """
    @brief Unload a Freebox config entry.
    
    @param hass The Home Assistant instance
    @param entry The config entry to unload
    @return True if unload was successful
    """
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        # Close API connection and remove deprecated reboot service
        await entry.runtime_data.close()
        hass.services.async_remove(DOMAIN, SERVICE_REBOOT)

    return unload_ok
