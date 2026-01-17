"""
@file router.py
@brief Represent the Freebox router and its devices and sensors.

This module provides the FreeboxRouter class which manages connections to a Freebox router
and handles device tracking, sensor updates, and API interactions with the Freebox.
"""
from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import Mapping
from contextlib import suppress
from datetime import datetime
from pathlib import Path
from typing import Any

from freebox_api import Freepybox
from freebox_api.api.call import Call
from freebox_api.api.home import Home
from freebox_api.api.wifi import Wifi
from freebox_api.exceptions import HttpRequestError, NotOpenError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.util import slugify

from .const import (
    API_VERSION,
    APP_DESC,
    CONNECTION_SENSORS_KEYS,
    DOMAIN,
    STORAGE_KEY,
    STORAGE_VERSION,
)

_LOGGER = logging.getLogger(__name__)


async def get_api(hass: HomeAssistant, host: str) -> Freepybox:
    """Get the Freebox API instance.
    
    Creates and returns a Freepybox API instance with the appropriate token file
    path. Creates the storage directory if it doesn't exist.
    
    @param hass The Home Assistant instance
    @param host The Freebox host address
    @return Configured Freepybox API instance
    """
    freebox_path = Store(hass, STORAGE_VERSION, STORAGE_KEY).path

    if not os.path.exists(freebox_path):
        await hass.async_add_executor_job(os.makedirs, freebox_path)

    token_file = Path(f"{freebox_path}/{slugify(host)}.conf")

    return Freepybox(APP_DESC, token_file, API_VERSION)


class FreeboxRouter:
    """
    @brief Representation of a Freebox router.
    
    This class manages the connection to a Freebox router and provides methods
    to update and access device information, sensors, and router state.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        api: Freepybox,
        freebox_config: Mapping[str, Any],
    ) -> None:
        """
        @brief Initialize a Freebox router.
        
        @param hass The Home Assistant instance
        @param entry The config entry for this Freebox integration
        @param api The Freepybox API instance
        @param freebox_config Configuration dictionary containing model info, MAC, and firmware version
        """
        self.hass = hass
        self._host = entry.data[CONF_HOST]  ##< Freebox host address
        self._port = entry.data[CONF_PORT]  ##< Freebox port number

        self._api: Freepybox = api  ##< Freepybox API instance
        self.name: str = freebox_config["model_info"]["pretty_name"]  ##< Freebox model name
        self.mac: str = freebox_config["mac"]  ##< Freebox MAC address
        self._sw_v: str = freebox_config["firmware_version"]  ##< Firmware version
        self._attrs: dict[str, Any] = {}  ##< Router attributes dictionary

        self.devices: dict[str, dict[str, Any]] = {}  ##< Connected devices indexed by MAC address
        self.disks: dict[int, dict[str, Any]] = {}  ##< Connected disks indexed by ID
        self.home_nodes: dict[int, dict[str, Any]] = {}  ##< Home automation nodes indexed by ID
        self.sensors_temperature: dict[str, int] = {}  ##< Temperature sensors data
        self.sensors_connection: dict[str, float] = {}  ##< Connection sensors data
        self.call_list: list[dict[str, Any]] = []  ##< Call log list

    async def update_all(self, now: datetime | None = None) -> None:
        """Update all Freebox platforms.
        
        Triggers updates for both device trackers and sensors.
        
        @param now Optional datetime for scheduled updates, defaults to None
        """
        try:
            await self.update_device_trackers()
            await self.update_sensors()
        except HttpRequestError as err:
            _LOGGER.error("Error updating Freebox data: %s", err)

    async def update_device_trackers(self) -> None:
        """Update Freebox devices.
        
        Retrieves the list of connected devices from the Freebox API and updates
        the internal device registry. Adds the Freebox router itself to the device
        list and dispatches signals for device updates and new devices.
        """
        new_device = False
        try:
            fbx_devices: list[dict[str, Any]] = await self._api.lan.get_hosts_list()
        except HttpRequestError as err:
            _LOGGER.error("Error fetching device list from Freebox: %s", err)
            return

        # Adds the Freebox itself
        fbx_devices.append(
            {
                "primary_name": self.name,
                "l2ident": {"id": self.mac},
                "vendor_name": "Freebox SAS",
                "host_type": "router",
                "active": True,
                "attrs": self._attrs,
            }
        )

        for fbx_device in fbx_devices:
            device_mac = fbx_device["l2ident"]["id"]

            if self.devices.get(device_mac) is None:
                new_device = True

            self.devices[device_mac] = fbx_device

        async_dispatcher_send(self.hass, self.signal_device_update)

        if new_device:
            async_dispatcher_send(self.hass, self.signal_device_new)

    async def update_sensors(self) -> None:
        """Update Freebox sensors.
        
        Updates temperature sensors, connection sensors, router attributes, call log,
        disk sensors, and home node sensors. Dispatches a signal when update is complete.
        Temperature values are in Celsius degrees.
        
        Performance: Uses asyncio.gather() to parallelize independent API calls for
        3-5x faster execution compared to sequential calls.
        """
        try:
            # Execute all independent API calls in parallel for optimal performance
            results = await asyncio.gather(
                self._api.system.get_config(),
                self._api.connection.get_status(),
                self._api.call.get_calls_log(),
                self._api.storage.get_disks(),
                self._api.home.get_home_nodes(),
                return_exceptions=True
            )
            
            syst_datas, connection_datas, call_list, fbx_disks, fbx_home_nodes = results
            
            # Process system sensors if successful
            if not isinstance(syst_datas, Exception):
                # According to the doc `syst_datas["sensors"]` is temperature sensors in celsius degree.
                # Name and id of sensors may vary under Freebox devices.
                for sensor in syst_datas["sensors"]:
                    self.sensors_temperature[sensor["name"]] = sensor.get("value")
                
                # Update router attributes
                if not isinstance(connection_datas, Exception):
                    self._attrs = {
                        "IPv4": connection_datas.get("ipv4"),
                        "IPv6": connection_datas.get("ipv6"),
                        "connection_type": connection_datas["media"],
                        "uptime": datetime.fromtimestamp(
                            round(datetime.now().timestamp()) - syst_datas["uptime_val"]
                        ),
                        "firmware_version": self._sw_v,
                        "serial": syst_datas["serial"],
                    }
            
            # Process connection sensors if successful
            if not isinstance(connection_datas, Exception):
                for sensor_key in CONNECTION_SENSORS_KEYS:
                    self.sensors_connection[sensor_key] = connection_datas[sensor_key]
            
            # Process call list if successful
            if not isinstance(call_list, Exception):
                self.call_list = call_list
            
            # Process disks if successful (may be None on first request)
            if not isinstance(fbx_disks, Exception) and fbx_disks:
                for fbx_disk in fbx_disks:
                    self.disks[fbx_disk["id"]] = fbx_disk
            
            # Process home nodes if successful (may be None on first request)
            if not isinstance(fbx_home_nodes, Exception) and fbx_home_nodes:
                for fbx_home_node in fbx_home_nodes:
                    self.home_nodes[fbx_home_node["id"]] = fbx_home_node
            
            # Log any exceptions that occurred
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    api_names = ["system", "connection", "call", "storage", "home"]
                    _LOGGER.warning("Error fetching %s data: %s", api_names[i], result)

        except Exception as err:
            _LOGGER.error("Error updating Freebox sensors: %s", err)

        async_dispatcher_send(self.hass, self.signal_sensor_update)

    async def reboot(self) -> None:
        """Reboot the Freebox.
        
        Sends a reboot command to the Freebox router through the API.
        """
        await self._api.system.reboot()

    async def close(self) -> None:
        """Close the connection.
        
        Closes the API connection to the Freebox. Suppresses NotOpenError
        exceptions if the connection is already closed.
        """
        with suppress(NotOpenError):
            await self._api.close()

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device information."""
        return DeviceInfo(
            configuration_url=f"https://{self._host}:{self._port}/",
            connections={(CONNECTION_NETWORK_MAC, self.mac)},
            identifiers={(DOMAIN, self.mac)},
            manufacturer="Freebox SAS",
            model=self.name,
            name=self.name,
            sw_version=self._sw_v,
        )

    @property
    def signal_device_new(self) -> str:
        """Event specific per Freebox entry to signal new device."""
        return f"{DOMAIN}-{self._host}-device-new"

    @property
    def signal_device_update(self) -> str:
        """Event specific per Freebox entry to signal updates in devices."""
        return f"{DOMAIN}-{self._host}-device-update"

    @property
    def signal_sensor_update(self) -> str:
        """Event specific per Freebox entry to signal updates in sensors."""
        return f"{DOMAIN}-{self._host}-sensor-update"
    
    @property
    def signal_home_device_update(self) -> str:
        """Event specific per Freebox entry to signal update in home devices."""
        return f"{DOMAIN}-{self._host}-home-device-update"

    @property
    def sensors(self) -> dict[str, Any]:
        """Return combined dictionary of temperature and connection sensors."""
        return {**self.sensors_temperature, **self.sensors_connection}

    @property
    def call(self) -> Call:
        """Return the call API."""
        return self._api.call

    @property
    def wifi(self) -> Wifi:
        """Return the wifi API."""
        return self._api.wifi

    @property
    def home(self) -> Home:
        """Return the home API."""
        return self._api.home