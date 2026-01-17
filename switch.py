"""
@file switch.py
@brief Support for Freebox Delta, Revolution and Mini 4K switch entities.

This module provides switch entity implementations for Freebox routers,
including WiFi control switches and home automation node switches.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from freebox_api.exceptions import InsufficientPermissionsError

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .router import FreeboxRouter

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """
    @brief Set up the Freebox switch entities.
    
    @param hass The Home Assistant instance.
    @param entry The config entry for this integration.
    @param async_add_entities Callback to add entities to Home Assistant.
    @return None
    """
    router: FreeboxRouter = hass.data[DOMAIN][entry.unique_id]

    entities = []

    entities.append(FreeboxWifiSwitch(router))

    _LOGGER.info(
        "%s - %s - %s home node(s)", router.name, router.mac, len(router.home_nodes)
    )

    for home_node in router.home_nodes.values():
        if home_node["category"] != "shutter":
            for endpoint in home_node.get("show_endpoints"):
                if endpoint["ep_type"] == "slot" and endpoint["value_type"] == "bool":
                    entities.append(
                        FreeboxHomeNodeSwitch(
                            router,
                            home_node,
                            endpoint,
                            endpoint["name"],
                        )
                    )

    async_add_entities(entities, True)


class FreeboxSwitch(SwitchEntity):
    """
    @brief Representation of a Freebox switch.
    
    Base class for Freebox switch entities with common functionality.
    """

    _attr_should_poll = False  ##< Disable polling for this entity

    def __init__(
        self,
        router: FreeboxRouter,
        endpoint_name: str,
        unik: Any,
    ) -> None:
        """
        @brief Initialize a Freebox switch.
        
        @param router The FreeboxRouter instance.
        @param endpoint_name The name of the endpoint.
        @param unik Unique identifier for the switch.
        @return None
        """
        self.entity_description = SwitchEntityDescription(
            key="switch", name=endpoint_name
        )
        self._router = router
        self._unik = unik
        self._attr_unique_id = f"{router.mac} {endpoint_name} {unik}"

    @callback
    def async_update_state(self) -> None:
        """
        @brief Update the Freebox switch state.
        
        @return None
        """
        # state = self._router.sensors[self.entity_description.key]
        # self._attr_is_on = state

    @property
    def device_info(self) -> DeviceInfo:
        """
        @brief Return the device information.
        
        @return DeviceInfo object containing device details.
        """
        return self._router.device_info

    @callback
    def async_on_demand_update(self) -> None:
        """
        @brief Update state on demand.
        
        @return None
        """
        self.async_update_state()
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Register state update callback.
        
        Called when entity is added to Home Assistant.
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


class FreeboxHomeNodeSwitch(FreeboxSwitch):
    """
    @brief Representation of a Freebox Home node switch.
    
    Switch entity for controlling Freebox home automation nodes.
    """

    def __init__(
        self,
        router: FreeboxRouter,
        home_node: dict[str, Any],
        endpoint: dict[str, Any],
        description: SwitchEntityDescription,
    ) -> None:
        """
        @brief Initialize a Freebox Home node switch.
        
        @param router The FreeboxRouter instance.
        @param home_node Dictionary containing home node information.
        @param endpoint Dictionary containing endpoint information.
        @param description Switch entity description.
        @return None
        """
        super().__init__(router, description, f"{home_node['id']} {endpoint['id']}")
        self._home_node = home_node
        self._endpoint = endpoint
        self._attr_name = f"{home_node['label']} {endpoint['name']}"
        self._unique_id = f"{self._router.mac} {endpoint['name']} {self._home_node['id']} {endpoint['id']}"
        self._enabled = None  ##< Current enabled state of the switch
        self._get_endpoint_id = None  ##< ID of the endpoint used for getting state

        # Discover for get endpoint
        for endpoint_candidate in home_node.get("show_endpoints"):
            if (
                endpoint_candidate["name"] == endpoint["name"]
                and endpoint_candidate["ep_type"] == "signal"
            ):
                self._get_endpoint_id = endpoint_candidate["id"]
                break

    @property
    def device_info(self) -> DeviceInfo:
        """
        @brief Return the device information.
        
        @return DeviceInfo object containing device details including firmware version.
        """
        fw_version = None
        if "props" in self._home_node:
            props = self._home_node["props"]
            if "FwVersion" in props:
                fw_version = props["FwVersion"]

        return DeviceInfo(
            identifiers={(DOMAIN, self._home_node["id"])},
            model=f'{self._home_node["category"]}',
            name=f"{self._home_node['label']}",
            sw_version=fw_version,
            via_device=(
                DOMAIN,
                self._router.mac,
            ),
            manufacturer="Freebox SAS",
        )

    @property
    def is_on(self) -> bool:
        """
        @brief Return true if device is on.
        
        @return True if the switch is on, False otherwise.
        """
        return self._enabled

    @callback
    def async_update_state(self) -> None:
        """
        @brief Update the Freebox Home node switch state.
        
        @return None
        """
        current_home_node = self._router.home_nodes.get(self._home_node.get("id"))
        if current_home_node.get("show_endpoints"):
            for end_point in current_home_node["show_endpoints"]:
                if self._get_endpoint_id == end_point["id"]:
                    self._enabled = end_point["value"]
                    break
        self._attr_is_on = self._enabled

    async def _async_set_state(self, enabled: bool) -> None:
        """Turn the switch on or off.
        
        @param enabled True to turn on, False to turn off.
        @return None
        """
        value_enabled = {"value": enabled}
        try:
            await self._router._api.home.set_home_endpoint_value(
                self._home_node["id"], self._endpoint["id"], value_enabled
            )
            self._enabled = enabled
        except InsufficientPermissionsError as err:
            _LOGGER.warning(
                "Home Assistant does not have permissions to modify the Freebox settings. Please refer to documentation: %s",
                err,
            )
        except asyncio.TimeoutError as err:
            _LOGGER.error(
                "Timeout setting home endpoint value for %s (id=%s, endpoint_id=%s): %s",
                self._attr_name,
                self._home_node["id"],
                self._endpoint["id"],
                err,
            )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on.
        
        @param kwargs Additional keyword arguments.
        @return None
        """
        await self._async_set_state(True)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off.
        
        @param kwargs Additional keyword arguments.
        @return None
        """
        await self._async_set_state(False)
        self.async_write_ha_state()

    async def async_update(self) -> None:
        """Update the entity state.
        
        Note: This is a lifecycle method and should not return a value.
        """
        # async_update should just update internal state, not return


class FreeboxWifiSwitch(SwitchEntity):
    """Representation of a Freebox WiFi switch.
    
    Switch entity for controlling the Freebox router WiFi functionality.
    """

    def __init__(self, router: FreeboxRouter) -> None:
        """Initialize the WiFi switch.
        
        @param router The FreeboxRouter instance.
        @return None
        """
        self._name = "Freebox WiFi"  ##< Name of the WiFi switch entity
        self._state: bool | None = None  ##< Current state of the WiFi (on/off)
        self._router = router  ##< Reference to the Freebox router
        self._unique_id = f"{self._router.mac} {self._name}"  ##< Unique identifier for the entity

    @property
    def unique_id(self) -> str:
        """
        @brief Return a unique ID.
        
        @return Unique identifier string for the entity.
        """
        return self._unique_id

    @property
    def name(self) -> str:
        """
        @brief Return the name of the switch.
        
        @return The switch entity name.
        """
        return self._name

    @property
    def is_on(self) -> bool | None:
        """
        @brief Return true if device is on.
        
        @return True if WiFi is on, False if off, None if unknown.
        """
        return self._state

    @property
    def device_info(self) -> DeviceInfo:
        """
        @brief Return the device information.
        
        @return DeviceInfo object containing device details.
        """
        return self._router.device_info

    async def _async_set_state(self, enabled: bool) -> None:
        """Turn the switch on or off.
        
        @param enabled True to turn on WiFi, False to turn off.
        @return None
        """
        wifi_config = {"enabled": enabled}
        try:
            await self._router.wifi.set_global_config(wifi_config)
        except InsufficientPermissionsError as err:
            _LOGGER.warning(
                "Home Assistant does not have permissions to modify WiFi settings: %s", err
            )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on.
        
        @param kwargs Additional keyword arguments.
        @return None
        """
        await self._async_set_state(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off.
        
        @param kwargs Additional keyword arguments.
        @return None
        """
        await self._async_set_state(False)

    async def async_update(self) -> None:
        """Get the state and update it.
        
        Fetches the current WiFi state from the router.
        @return None
        """
        datas = await self._router.wifi.get_global_config()
        active = datas["enabled"]
        self._state = bool(active)
