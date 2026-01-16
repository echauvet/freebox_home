"""
@file router.py
@brief Represent the Freebox router and its devices and sensors.

This module provides the FreeboxRouter class which manages connections to a Freebox router
and handles device tracking, sensor updates, and API interactions with the Freebox.
"""
from __future__ import annotations

from collections.abc import Mapping
from contextlib import suppress
from datetime import datetime

import os
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
from homeassistant.util import slugify
from homeassistant.helpers.storage import Store

from .const import (
    API_VERSION,
    APP_DESC,
    CONNECTION_SENSORS_KEYS,
    DOMAIN,
    STORAGE_KEY,
    STORAGE_VERSION,
)


async def get_api(hass: HomeAssistant, host: str) -> Freepybox:
    """
    @brief Get the Freebox API instance.
    
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
        """
        @brief Update all Freebox platforms.
        
        Triggers updates for both device trackers and sensors.
        
        @param now Optional datetime for scheduled updates, defaults to None
        """
        await self.update_device_trackers()
        await self.update_sensors()

    async def update_device_trackers(self) -> None:
        """
        @brief Update Freebox devices.
        
        Retrieves the list of connected devices from the Freebox API and updates
        the internal device registry. Adds the Freebox router itself to the device
        list and dispatches signals for device updates and new devices.
        """
        new_device = False
        fbx_devices: list[dict[str, Any]] = await self._api.lan.get_hosts_list()

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
        
        Updates temperature sensors, connection sensors, router attributes, call log,
        disk sensors, and home node sensors. Dispatches a signal when update is complete.
        Temperature values are in Celsius degrees.
        """
        # System sensors
        syst_datas: dict[str, Any] = await self._api.system.get_config()

        # According to the doc `syst_datas["sensors"]` is temperature sensors in celsius degree.
        # Name and id of sensors may vary under Freebox devices.
        for sensor in syst_datas["sensors"]:
            self.sensors_temperature[sensor["name"]] = sensor.get("value")

        # Connection sensors
        connection_datas: dict[str, Any] = await self._api.connection.get_status()
        for sensor_key in CONNECTION_SENSORS_KEYS:
            self.sensors_connection[sensor_key] = connection_datas[sensor_key]

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

        self.call_list = await self._api.call.get_calls_log()

        await self._update_disks_sensors()
        await self._update_home_nodes_sensors()

        async_dispatcher_send(self.hass, self.signal_sensor_update)

    async def _update_disks_sensors(self) -> None:
        """
        @brief Update Freebox disks.
        
        Retrieves the list of connected storage disks from the Freebox API
        and updates the internal disks registry. May return empty list on first request.
        """
        # None at first request
        fbx_disks: list[dict[str, Any]] = await self._api.storage.get_disks() or []

        for fbx_disk in fbx_disks:
            self.disks[fbx_disk["id"]] = fbx_disk

    async def _update_home_nodes_sensors(self) -> None:
        """
        @brief Update Freebox home nodes.
        
        Retrieves the list of home automation nodes from the Freebox API
        and updates the internal home nodes registry. May return empty list on first request.
        """
        # None at first request
        fbx_home_nodes: list[dict[str, Any]] = (
            await self._api.home.get_home_nodes() or []
        )

        for fbx_home_node in fbx_home_nodes:
            self.home_nodes[fbx_home_node["id"]] = fbx_home_node

    async def reboot(self) -> None:
        """
        @brief Reboot the Freebox.
        
        Sends a reboot command to the Freebox router through the API.
        """
        await self._api.system.reboot()

    async def close(self) -> None:
        """
        @brief Close the connection.
        
        Closes the API connection to the Freebox. Suppresses NotOpenError
        exceptions if the connection is already closed.
        """
        with suppress(NotOpenError):
            await self._api.close()

    @property
    def device_info(self) -> DeviceInfo:
        """
        @brief Return the device information.
        
        @return DeviceInfo object containing router identification and configuration details
        """
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
        """
        @brief Event specific per Freebox entry to signal new device.
        
        @return Signal string for dispatching new device events
        """
        return f"{DOMAIN}-{self._host}-device-new"

    @property
    def signal_device_update(self) -> str:
        """
        @brief Event specific per Freebox entry to signal updates in devices.
        
        @return Signal string for dispatching device update events
        """
        return f"{DOMAIN}-{self._host}-device-update"

    @property
    def signal_sensor_update(self) -> str:
        """
        @brief Event specific per Freebox entry to signal updates in sensors.
        
        @return Signal string for dispatching sensor update events
        """
        return f"{DOMAIN}-{self._host}-sensor-update"
    
    @property
    def signal_home_device_update(self) -> str:
        """
        @brief Event specific per Freebox entry to signal update in home devices.
        
        @return Signal string for dispatching home device update events
        """
        return f"{DOMAIN}-{self._host}-home-device-update"


    @property
    def sensors(self) -> dict[str, Any]:
        """
        @brief Return sensors.
        
        @return Combined dictionary of temperature and connection sensors
        """
        return {**self.sensors_temperature, **self.sensors_connection}

    @property
    def call(self) -> Call:
        """
        @brief Return the call API.
        
        @return Call API instance for accessing call-related functionality
        """
        return self._api.call

    @property
    def wifi(self) -> Wifi:
        """
        @brief Return the wifi API.
        
        @return Wifi API instance for accessing WiFi-related functionality
        """
        return self._api.wifi

    @property
    def home(self) -> Home:
        """
        @brief Return the home API.
        
        @return Home API instance for accessing home automation functionality
        """
        return self._api.home