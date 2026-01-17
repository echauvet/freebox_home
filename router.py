"""
@file router.py
@brief Represent the Freebox router and its devices and sensors.

This module provides the FreeboxRouter class which manages connections to a Freebox router
and handles device tracking, sensor updates, and API interactions with the Freebox.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from collections.abc import Callable, Mapping
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
    HOME_COMPATIBLE_CATEGORIES,
    STORAGE_KEY,
    STORAGE_VERSION,
)

_LOGGER = logging.getLogger(__name__)


def is_json(json_str: str) -> bool:
    """
    @brief Check whether a string is valid JSON.

    @param[in] json_str Candidate string to validate
    @return True when json_str contains valid JSON, False otherwise
    """
    try:
        json.loads(json_str)
    except ValueError:
        return False
    return True


async def get_hosts_list_if_supported(
    fbx_api: Freepybox,
) -> tuple[bool, list[dict[str, Any]]]:
    """
    @brief Get hosts list if supported by the Freebox.

    Some Freebox configurations (like bridge mode) do not support the hosts list API.
    Handles the error gracefully and returns an empty list when unsupported.

    @param[in] fbx_api Freepybox API instance used for the request
    @return Tuple of (is_supported flag, hosts list)
    """
    hosts_list: list[dict[str, Any]] = []

    try:
        hosts_list = await fbx_api.lan.get_hosts_list()
    except HttpRequestError as err:
        # Freebox in bridge mode will refuse to return hosts list
        # Error will be like: "Request failed (APIResponse: {\"success\": false, \"msg\": \"Erreur lors de la récupération de la liste des hosts lan (nodev)\", \"error_code\": \"nodev\"})"
        error_msg = str(err)
        # Try to extract error_code from the response
        if is_json(error_msg[error_msg.find("{") :]):
            error_data = json.loads(error_msg[error_msg.find("{") :])
            if error_data.get("error_code") == "nodev":
                _LOGGER.warning("Hosts list not supported (bridge mode?)")
                return (False, [])

        # Unknown error, re-raise
        _LOGGER.error("Error fetching hosts list: %s", err)
        raise

    return (True, hosts_list)


FreeboxConfigEntry = ConfigEntry["FreeboxRouter"]


async def get_api(hass: HomeAssistant, host: str) -> Freepybox:
    """
    @brief Get the Freebox API instance.

    Creates and returns a Freepybox API instance with the appropriate token
    file path. Ensures the storage directory exists prior to instantiation.

    @param[in] hass Home Assistant instance providing storage access
    @param[in] host Freebox host address used for token file naming
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
        
        @param[in] hass Home Assistant instance coordinating integration services
        @param[in] entry Config entry for this Freebox integration
        @param[in] api Freepybox API instance already authenticated/opened
        @param[in] freebox_config Mapping containing model info, MAC, and firmware version
        @return None
        """
        self.hass = hass
        self._host = entry.data[CONF_HOST]  ##< Freebox host address
        self._port = entry.data[CONF_PORT]  ##< Freebox port number

        self._api: Freepybox = api  ##< Freepybox API instance
        self.name: str = freebox_config["model_info"]["pretty_name"]  ##< Freebox model name
        self.mac: str = freebox_config["mac"]  ##< Freebox MAC address
        self._sw_v: str = freebox_config["firmware_version"]  ##< Firmware version
        self._attrs: dict[str, Any] = {}  ##< Router attributes dictionary
        self.model_id: str = freebox_config["model_info"]["name"]  ##< Model ID
        self.hw_version: str = freebox_config.get("board_name", "Unknown")  ##< Hardware version

        self.supports_hosts: bool = True  ##< Whether router supports hosts list API
        self.supports_raid: bool = True  ##< Whether router supports RAID arrays

        self.devices: dict[str, dict[str, Any]] = {}  ##< Connected devices indexed by MAC address
        self.disks: dict[int, dict[str, Any]] = {}  ##< Connected disks indexed by ID
        self.raids: dict[int, dict[str, Any]] = {}  ##< RAID arrays indexed by ID
        self.home_nodes: dict[int, dict[str, Any]] = {}  ##< Home automation nodes indexed by ID
        self.sensors_temperature: dict[str, int] = {}  ##< Temperature sensors data
        self.sensors_connection: dict[str, float] = {}  ##< Connection sensors data
        self.call_list: list[dict[str, Any]] = []  ##< Call log list
        
        self.home_granted: bool = False  ##< Whether home automation permission is granted
        self.home_devices: dict[int, dict[str, Any]] = {}  ##< Home automation devices indexed by ID
        self.listeners: list[Callable[[], None]] = []  ##< List of cleanup listeners
        self._home_permission_logged: bool = False  ##< Track if home permission error was logged

    async def update_all(self, now: datetime | None = None) -> None:
        """
        @brief Update all Freebox platforms.

        Triggers updates for device trackers, sensors, and home devices.
        Called periodically via async_track_time_interval.

        @param[in] now Optional datetime for scheduled updates (unused)
        @return None
        @see update_device_trackers
        @see update_sensors
        @see update_home_devices
        """
        try:
            _LOGGER.debug("Starting Freebox update cycle for %s", self._host)
            await self.update_device_trackers()
            await self.update_sensors()
            await self.update_home_devices()
            _LOGGER.debug("Completed Freebox update cycle for %s", self._host)
        except HttpRequestError as err:
            _LOGGER.error("Error updating Freebox data for %s: %s", self._host, err)

    async def update_device_trackers(self) -> None:
        """
        @brief Update Freebox devices.

        Retrieves the list of connected devices from the Freebox API and updates
        the internal device registry. Adds the Freebox router itself to the device
        list and dispatches signals for device updates and new devices. Handles
        bridge mode scenarios where the hosts list API is unavailable.

        @return None
        @see get_hosts_list_if_supported
        """
        new_device = False
        
        # Use the helper function to handle bridge mode gracefully
        self.supports_hosts, fbx_devices = await get_hosts_list_if_supported(self._api)
        
        if not self.supports_hosts:
            # In bridge mode, we can't get the hosts list
            # Just dispatch an update signal and return
            async_dispatcher_send(self.hass, self.signal_device_update)
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
        """
        @brief Update Freebox sensors.

        Refreshes temperature sensors, connection sensors, router attributes,
        call log, disk sensors, RAID sensors, and home node sensors. Dispatches
        a signal when the update completes. Temperature values are reported in
        Celsius degrees. API calls are executed sequentially with dedicated
        error handling per sensor type.

        @return None
        """
        try:
            sensor_count = 0
            
            # System sensors (temperature)
            try:
                syst_datas = await self._api.system.get_config()
                # According to the doc `syst_datas["sensors"]` is temperature sensors in celsius degree.
                # Name and id of sensors may vary under Freebox devices.
                for sensor in syst_datas["sensors"]:
                    self.sensors_temperature[sensor["name"]] = sensor.get("value")
                sensor_count += len(syst_datas["sensors"])
            except HttpRequestError as err:
                _LOGGER.warning("Error fetching system data for %s: %s", self._host, err)
                syst_datas = None

            # Connection sensors
            try:
                connection_datas = await self._api.connection.get_status()
                for sensor_key in CONNECTION_SENSORS_KEYS:
                    self.sensors_connection[sensor_key] = connection_datas[sensor_key]
                sensor_count += len(CONNECTION_SENSORS_KEYS)
            except HttpRequestError as err:
                _LOGGER.warning("Error fetching connection data for %s: %s", self._host, err)
                connection_datas = None

            # Update router attributes if both system and connection data available
            if syst_datas and connection_datas:
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

            # Call list
            try:
                self.call_list = await self._api.call.get_calls_log()
            except HttpRequestError as err:
                _LOGGER.warning("Error fetching call log for %s: %s", self._host, err)

            # Disk sensors
            await self._update_disks_sensors()
            
            # RAID sensors
            await self._update_raids_sensors()

            # Home nodes
            try:
                fbx_home_nodes = await self._api.home.get_home_nodes()
                if fbx_home_nodes:
                    for fbx_home_node in fbx_home_nodes:
                        self.home_nodes[fbx_home_node["id"]] = fbx_home_node
                    _LOGGER.debug("Updated %d home nodes for %s", len(fbx_home_nodes), self._host)
            except HttpRequestError as err:
                _LOGGER.warning("Error fetching home nodes for %s: %s", self._host, err)

            _LOGGER.debug("Updated %d sensors for %s", sensor_count, self._host)

        except Exception as err:
            _LOGGER.error("Error updating Freebox sensors for %s: %s", self._host, err)

        async_dispatcher_send(self.hass, self.signal_sensor_update)

    async def _update_disks_sensors(self) -> None:
        """
        @brief Update Freebox disk sensors.

        Fetches disk information including partitions and processes them into
        a structured dictionary indexed by disk ID.

        @return None
        """
        try:
            fbx_disks = await self._api.storage.get_disks()
            if fbx_disks:
                for fbx_disk in fbx_disks:
                    self.disks[fbx_disk["id"]] = fbx_disk
        except HttpRequestError as err:
            _LOGGER.warning("Error fetching disk data: %s", err)

    async def _update_raids_sensors(self) -> None:
        """
        @brief Update Freebox RAID sensors.

        Fetches RAID array information if supported by the Freebox model and
        disables further calls when the API endpoint is unavailable.

        @return None
        """
        if not self.supports_raid:
            return

        try:
            fbx_raids = await self._api.storage.get_raids()
            if fbx_raids:
                for fbx_raid in fbx_raids:
                    self.raids[fbx_raid["id"]] = fbx_raid
        except HttpRequestError as err:
            # Some Freebox models don't support RAID
            error_msg = str(err)
            if "unknown function" in error_msg.lower():
                _LOGGER.info("RAID not supported on this Freebox model")
                self.supports_raid = False
            else:
                _LOGGER.warning("Error fetching RAID data: %s", err)

    async def update_home_devices(self) -> None:
        """
        @brief Update Freebox home automation devices.

        Fetches home automation devices (sensors, switches, etc.) from the Freebox
        when the integration has home permission. Dispatches signals for device
        updates and newly discovered devices.

        @return None
        """
        if not self.home_granted:
            # Check if we have home automation permission
            try:
                permissions = await self._api.get_permissions()
                self.home_granted = permissions.get("home", False)
            except HttpRequestError as err:
                _LOGGER.warning("Error checking home permissions: %s", err)
                return

        if not self.home_granted:
            if not self._home_permission_logged:
                _LOGGER.error(
                    "Home automation permission not granted. "
                    "Please grant 'home' permission in the Freebox configuration to access home devices."
                )
                self._home_permission_logged = True
            return

        try:
            # Get all home devices
            new_device = False
            fbx_home_devices = await self._api.home.get_home_nodes()
            
            if fbx_home_devices:
                for fbx_home_device in fbx_home_devices:
                    device_id = fbx_home_device["id"]
                    
                    # Check if this is a new device
                    if device_id not in self.home_devices:
                        new_device = True
                    
                    # Store device data
                    self.home_devices[device_id] = fbx_home_device

            # Dispatch update signals
            async_dispatcher_send(self.hass, self.signal_home_device_update)
            
            if new_device:
                async_dispatcher_send(self.hass, self.signal_home_device_new)

        except HttpRequestError as err:
            _LOGGER.warning("Error fetching home devices: %s", err)

    async def reboot(self) -> None:
        """
        @brief Reboot the Freebox router.

        Sends a reboot command via the system API.

        @return None
        """
        await self._api.system.reboot()

    async def close(self) -> None:
        """
        @brief Close the API connection to the Freebox.

        Closes the API connection and suppresses NotOpenError when already closed.

        @return None
        """
        with suppress(NotOpenError):
            await self._api.close()

    @property
    def device_info(self) -> DeviceInfo:
        """
        @brief Return metadata describing the Freebox router.

        @return DeviceInfo object with identifiers, firmware, and links
        """
        return DeviceInfo(
            configuration_url=f"https://{self._host}:{self._port}/",
            connections={(CONNECTION_NETWORK_MAC, self.mac)},
            identifiers={(DOMAIN, self.mac)},
            manufacturer="Freebox SAS",
            model=self.name,
            model_id=self.model_id,
            name=self.name,
            sw_version=self._sw_v,
            hw_version=self.hw_version,
        )

    @property
    def signal_device_new(self) -> str:
        """
        @brief Dispatcher signal name for newly discovered devices.

        @return Unique signal identifier string
        """
        return f"{DOMAIN}-{self._host}-device-new"

    @property
    def signal_device_update(self) -> str:
        """
        @brief Dispatcher signal name for device updates.

        @return Unique signal identifier string
        """
        return f"{DOMAIN}-{self._host}-device-update"

    @property
    def signal_sensor_update(self) -> str:
        """
        @brief Dispatcher signal name for sensor updates.

        @return Unique signal identifier string
        """
        return f"{DOMAIN}-{self._host}-sensor-update"
    
    @property
    def signal_home_device_update(self) -> str:
        """
        @brief Dispatcher signal name for home device updates.

        @return Unique signal identifier string
        """
        return f"{DOMAIN}-{self._host}-home-device-update"

    @property
    def signal_home_device_new(self) -> str:
        """
        @brief Dispatcher signal name for newly discovered home devices.

        @return Unique signal identifier string
        """
        return f"{DOMAIN}-{self._host}-home-device-new"

    @property
    def sensors(self) -> dict[str, Any]:
        """
        @brief Return combined dictionary of temperature and connection sensors.

        @return Mapping of sensor keys to their current values
        """
        return {**self.sensors_temperature, **self.sensors_connection}

    @property
    def call(self) -> Call:
        """
        @brief Return the call API proxy.

        @return Freepybox Call API object
        """
        return self._api.call

    @property
    def wifi(self) -> Wifi:
        """
        @brief Return the WiFi API proxy.

        @return Freepybox Wifi API object
        """
        return self._api.wifi

    @property
    def home(self) -> Home:
        """
        @brief Return the home automation API proxy.

        @return Freepybox Home API object
        """
        return self._api.home