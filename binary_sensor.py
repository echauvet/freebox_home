"""
@file binary_sensor.py
@author Freebox Home Contributors
@brief Support for Freebox binary sensor entities.
@version 1.2.0.1

This module provides binary sensor entities for the Freebox Home Assistant integration,
including support for motion sensors, door/window sensors, and other binary state devices
from Freebox Home nodes.
"""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, HOME_NODES_BINARY_SENSORS, CATEGORY_TO_MODEL, FreeboxHomeCategory
from .router import FreeboxRouter

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Freebox binary sensors from a config entry.
    
    Discovers and creates binary sensor entities from Freebox Home nodes,
    including motion sensors (PIR) and door/window sensors (DWS).
    
    @param[in] hass Home Assistant instance coordinating the integration
    @param[in] entry Config entry providing router runtime data
    @param[in] async_add_entities Callback used to register entities with HA
    @return None
    @see FreeboxHomeNodeBinarySensor
    """
    router: FreeboxRouter = entry.runtime_data
    entities = []

    _LOGGER.debug(
        "%s - %s - %s home node(s)", router.name, router.mac, len(router.home_nodes)
    )

    for home_node in router.home_nodes.values():
        for endpoint in home_node.get("show_endpoints"):
            if endpoint["ep_type"] == "signal":
                if endpoint["name"] == "cover":
                    entities.append(
                        FreeboxHomeNodeBinarySensor(
                            router,
                            home_node,
                            endpoint,
                            HOME_NODES_BINARY_SENSORS[endpoint["name"]],
                        )
                    )
                elif endpoint["name"] == "trigger":
                    if home_node["category"] == FreeboxHomeCategory.PIR:
                        entities.append(
                            FreeboxHomeNodeBinarySensor(
                                router,
                                home_node,
                                endpoint,
                                HOME_NODES_BINARY_SENSORS["motion"],
                            )
                        )
                    elif home_node["category"] == FreeboxHomeCategory.DWS:
                        entities.append(
                            FreeboxHomeNodeBinarySensor(
                                router,
                                home_node,
                                endpoint,
                                HOME_NODES_BINARY_SENSORS["opening"],
                            )
                        )

    async_add_entities(entities, True)


class FreeboxBinarySensor(BinarySensorEntity):
    """
    @brief Representation of a Freebox binary sensor.
    
    Base class for Freebox binary sensor entities that monitors boolean state values.
    """

    _attr_should_poll = False  ##< Disable polling, state updates via dispatcher

    def __init__(
        self,
        router: FreeboxRouter,
        description: BinarySensorEntityDescription,
        unik: Any,
    ) -> None:
        """
        @brief Initialize a Freebox binary sensor.
        
        @param[in] router Freebox router instance providing sensor data
        @param[in] description Binary sensor entity description metadata
        @param[in] unik Unique identifier component for this sensor
        @return None
        """
        self.entity_description = description
        self._router = router
        self._unik = unik
        self._attr_unique_id = f"{router.mac} {description.name} {unik}"

    @callback
    def async_update_state(self) -> None:
        """
        @brief Update the Freebox binary sensor state.

        Fetches the current state from the router's sensor data and updates
        the entity's is_on attribute.

        @return None
        """
        state = self._router.sensors[self.entity_description.key]
        self._attr_is_on = state

    @property
    def device_info(self) -> DeviceInfo:
        """
        @brief Return the device information.

        @return DeviceInfo object containing device metadata for the router
        """
        return self._router.device_info

    @callback
    def async_on_demand_update(self) -> None:
        """
        @brief Update state on demand.

        Called when dispatcher signals a state change. Updates the sensor
        state and writes it to Home Assistant.

        @return None
        """
        self.async_update_state()
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Register state update callback when entity is added to Home Assistant.
        
        Performs initial state update and registers for dispatcher updates
        to keep the sensor state synchronized.
        
        @return None
        """
        self.async_update_state()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                self._router.signal_sensor_update,
                self.async_on_demand_update,
            )
        )


class FreeboxHomeNodeBinarySensor(FreeboxBinarySensor):
    """
    @brief Representation of a Freebox Home node binary sensor.
    
    Extended binary sensor class for Freebox Home node devices such as
    motion detectors and door/window sensors.
    """

    def __init__(
        self,
        router: FreeboxRouter,
        home_node: dict[str, Any],
        endpoint: dict[str, Any],
        description: BinarySensorEntityDescription,
    ) -> None:
        """
        @brief Initialize a Freebox Home node binary sensor.
        
        @param[in] router Freebox router instance providing sensor data
        @param[in] home_node Mapping containing home node information
        @param[in] endpoint Mapping containing endpoint metadata
        @param[in] description Binary sensor entity description metadata
        @return None
        """
        super().__init__(router, description, f"{home_node['id']} {endpoint['id']}")
        self._home_node = home_node
        self._endpoint = endpoint
        self._attr_name = f"{home_node['label']} {description.name}"
        self._unique_id = f"{self._router.mac} {description.key} {self._home_node['id']} {endpoint['id']}"

    @property
    def device_info(self) -> DeviceInfo:
        """
        @brief Return the device information for the home node.

        Extracts device metadata including model, firmware version, and manufacturer
        from the home node data.

        @return DeviceInfo object containing device metadata for the home node
        """
        fw_version = None
        if "props" in self._home_node:
            props = self._home_node["props"]
            if "FwVersion" in props:
                fw_version = props["FwVersion"]

        return DeviceInfo(
            identifiers = {(DOMAIN, self._home_node["id"])},
            model = CATEGORY_TO_MODEL.get(self._home_node["category"]),
            name = f"{self._home_node['label']}",
            sw_version = fw_version,
            via_device = (
                DOMAIN,
                self._router.mac,
            ),
            manufacturer="Freebox SAS",
        )

    @callback
    def async_update_state(self) -> None:
        """
        @brief Update the Freebox Home node binary sensor state.

        Retrieves the current endpoint value from the home node data and updates
        the sensor state. For trigger endpoints, the value is inverted.

        @return None
        """
        value = None

        current_home_node = self._router.home_nodes.get(self._home_node.get("id"))
        if current_home_node.get("show_endpoints"):
            for end_point in current_home_node["show_endpoints"]:
                if self._endpoint["id"] == end_point["id"]:
                    value = (
                        not end_point["value"]
                        if end_point["name"] == "trigger"
                        else end_point["value"]
                    )
                    break

        self._attr_is_on = value
