"""
@file cover.py
@author Freebox Home Contributors
@brief Support for Freebox Cover entities.
@version 1.2.0

This module provides Home Assistant cover platform integration for Freebox home automation devices,
including shutters, openers, and basic shutters. It handles position control and state management
for motorized covers connected to the Freebox home automation system.
"""
from __future__ import annotations

import logging
from typing import Any

from freebox_api.exceptions import InsufficientPermissionsError

from homeassistant.components.cover import (
    ATTR_POSITION,
    CoverEntity,
    CoverEntityDescription,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, HOME_NODES_COVERS
from .router import FreeboxRouter

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """
    @brief Set up Freebox cover entities from a config entry.

    Discovers cover-capable home nodes (shutters, openers, basic shutters)
    and instantiates dedicated entity classes for each supported node type.

    @param[in] hass Home Assistant instance coordinating the integration
    @param[in] entry Config entry providing router runtime data
    @param[in] async_add_entities Callback used to register entities with HA
    @return None
    @see FreeboxHomeNodeCover
    @see FreeboxHomeNodeBasicCover
    """
    router: FreeboxRouter = entry.runtime_data
    entities = []

    _LOGGER.debug(
        "%s - %s - %s home node(s)", router.name, router.mac, len(router.home_nodes)
    )

    for home_node in router.home_nodes.values():
        if home_node["category"] == "shutter":
            entities.append(
                FreeboxHomeNodeCover(
                    router,
                    home_node,
                    HOME_NODES_COVERS["shutter"],
                )
            )
        elif home_node["category"] == "opener":
            entities.append(
                FreeboxHomeNodeCover(
                    router,
                    home_node,
                    HOME_NODES_COVERS["opener"],
                )
            )
        elif home_node["category"] == "basic_shutter":
            entities.append(
                FreeboxHomeNodeBasicCover(
                    router,
                    home_node,
                    HOME_NODES_COVERS["basic_shutter"],
                )
            )

    async_add_entities(entities, True)


class FreeboxCover(CoverEntity):
    """
    @brief Base representation of a Freebox cover entity.
    
    This is the base class for all Freebox cover entities, providing common
    functionality for state updates and Home Assistant integration.
    """

    _attr_should_poll = False  ##< Disable polling for this entity

    def __init__(
        self,
        router: FreeboxRouter,
        description: CoverEntityDescription,
        unik: Any,
    ) -> None:
        """
        @brief Initialize a Freebox cover entity.
        
        @param[in] router FreeboxRouter instance managing the connection
        @param[in] description Cover entity description metadata
        @param[in] unik Unique identifier for the cover
        @return None
        """
        self.entity_description = description
        self._router = router
        self._unik = unik
        self._attr_unique_id = f"{router.mac} {description.name} {unik}"

    @callback
    def async_update_state(self) -> None:
        """
        @brief Update the state of the Freebox cover.

        Placeholder for subclasses to implement state synchronization logic.

        @return None
        """
        # state = self._router.sensors[self.entity_description.key]
        # self._attr = state

    @property
    def device_info(self) -> DeviceInfo:
        """
        @brief Return the device information for this cover.
        
        @return DeviceInfo object containing device metadata.
        """
        return self._router.device_info

    @callback
    def async_on_demand_update(self) -> None:
        """
        @brief Handle on-demand state updates.
        
        Updates the state and writes it to Home Assistant.
        
        @return None
        """
        self.async_update_state()
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Register state update callback when entity is added to Home Assistant.
        
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


class FreeboxHomeNodeCover(FreeboxCover):
    """
    @brief Representation of a Freebox Home node cover with position control.
    
    Supports shutters and openers with precise position control (0-100%),
    including open, close, stop, and set position commands.
    """

    def __init__(
        self,
        router: FreeboxRouter,
        home_node: dict[str, Any],
        description: CoverEntityDescription,
    ) -> None:
        """
        @brief Initialize a Freebox Home node cover with position control.
        
        @param[in] router FreeboxRouter instance managing the connection
        @param[in] home_node Mapping containing home node configuration and state
        @param[in] description Cover entity description metadata
        @return None
        """
        super().__init__(router, description, home_node["id"])
        self._home_node = home_node
        self._attr_name = f"{home_node['label']} {description.name}"
        self._unique_id = (
            f"{self._router.mac} {description.key} {self._home_node['id']}"
        )
        self._attr_supported_features = (
            CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP | CoverEntityFeature.SET_POSITION
        )

        self._position = None  ##< Current cover position (0-100%)
        # Discover for set/get endpoints
        for endpoint in home_node.get("show_endpoints"):
            if endpoint["name"] == "position_set":
                if endpoint["ep_type"] == "signal":
                    self._get_endpoint_id = endpoint["id"]
                elif endpoint["ep_type"] == "slot":
                    self._set_endpoint_id = endpoint["id"]
            elif endpoint["name"] == "stop" and endpoint["ep_type"] == "slot":
                self._stop_endpoint_id = endpoint["id"]

    @property
    def device_info(self) -> DeviceInfo:
        """
        @brief Return the device information for this home node cover.
        
        @return DeviceInfo object with manufacturer, model, firmware version, etc.
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

    @callback
    def async_update_state(self) -> None:
        """
        @brief Refresh the cover position and state from the router.
        
        Updates the internal position state from the latest router data.
        Note: Despite the None return type hint, this method returns a boolean
        indicating if the cover is closed (position == 0).
        """
        current_home_node = self._router.home_nodes.get(self._home_node.get("id"))
        if current_home_node.get("show_endpoints"):
            for end_point in current_home_node["show_endpoints"]:
                if end_point["id"] == self._get_endpoint_id:
                    self._position = 100 - end_point["value"]
        return self._position == 0

    @property
    def current_cover_position(self):
        """
        @brief Return the current cover position.
        
        @return Integer position value from 0 (closed) to 100 (open).
        """
        return self._position

    @property
    def is_closed(self):
        """
        @brief Check if the cover is closed.
        
        @return True if cover position is 0 (fully closed), False otherwise.
        """
        return self._position == 0

    async def set_position(self, position: int) -> None:
        """
        @brief Set the cover position.

        @param[in] position Target position from 0 (closed) to 100 (open)
        @return None
        """
        value_position = {"value": (100 - position)}
        try:
            await self._router._api.home.set_home_endpoint_value(
                self._home_node["id"], self._set_endpoint_id, value_position
            )
        except InsufficientPermissionsError as err:
            _LOGGER.warning(
                "Home Assistant does not have permissions to modify the Freebox settings: %s", err
            )

    async def get_position(self) -> int | None:
        """
        @brief Get the current cover position from the API.

        @return Integer position value from 0 (closed) to 100 (open)
        """
        try:
            ret = await self._router._api.home.get_home_endpoint_value(
                self._home_node["id"], self._get_endpoint_id
            )
            self._position = 100 - ret["value"]
        except InsufficientPermissionsError as err:
            _LOGGER.warning(
                "Home Assistant does not have permissions to modify the Freebox settings: %s", err
            )
        return self._position

    async def async_close_cover(self, **kwargs: Any) -> None:
        """
        @brief Close the cover completely.

        @param[in] kwargs Additional keyword arguments (unused)
        @return None
        """
        await self.set_position(0)
        self.async_write_ha_state()

    async def async_open_cover(self, **kwargs: Any) -> None:
        """
        @brief Open the cover completely.

        @param[in] kwargs Additional keyword arguments (unused)
        @return None
        """
        await self.set_position(100)
        self.async_write_ha_state()

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """
        @brief Set the cover to a specific position.

        @param[in] kwargs Keyword arguments containing ATTR_POSITION with target position
        @return None
        """
        await self.set_position(kwargs.get(ATTR_POSITION))
        self.async_write_ha_state()

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """
        @brief Stop the current cover movement.

        @param[in] kwargs Additional keyword arguments (unused)
        @return None
        """
        try:
            await self._router._api.home.set_home_endpoint_value(
                self._home_node["id"], self._stop_endpoint_id, {"value": True}
            )
        except InsufficientPermissionsError as err:
            _LOGGER.warning(
                "Home Assistant does not have permissions to modify the Freebox settings: %s", err
            )


class FreeboxHomeNodeBasicCover(FreeboxCover):
    """
    @brief Representation of a Freebox Home node basic cover with binary control.
    
    Supports basic shutters with simple up/down/stop control without precise
    position reporting (binary open/closed state only).
    """

    def __init__(
        self,
        router: FreeboxRouter,
        home_node: dict[str, Any],
        description: CoverEntityDescription,
    ) -> None:
        """
        @brief Initialize a Freebox Home node basic cover.
        
        @param[in] router FreeboxRouter instance managing the connection
        @param[in] home_node Mapping containing home node configuration and state
        @param[in] description Cover entity description metadata
        @return None
        """
        super().__init__(router, description, home_node["id"])
        self._home_node = home_node
        self._attr_name = f"{home_node['label']} {description.name}"
        self._unique_id = (
            f"{self._router.mac} {description.key} {self._home_node['id']}"
        )
        self._attr_supported_features = CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP
        

        self._position = None  ##< Binary position state (open/closed)
        # Discover for set/get endpoints
        for endpoint in home_node.get("show_endpoints"):
            if endpoint["name"] == "state" and endpoint["ep_type"] == "signal":
                self._get_state_endpoint_id = endpoint["id"]
            elif endpoint["ep_type"] == "slot":
                if endpoint["name"] == "stop":
                    self._stop_endpoint_id = endpoint["id"]
                elif endpoint["name"] == "up":
                    self._up_endpoint_id = endpoint["id"]
                elif endpoint["name"] == "down":
                    self._down_endpoint_id = endpoint["id"]

    @property
    def device_info(self) -> DeviceInfo:
        """
        @brief Return the device information for this basic cover.
        
        @return DeviceInfo object with manufacturer, model, firmware version, etc.
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

    @callback
    def async_update_state(self) -> None:
        """
        @brief Refresh the binary state (open/closed) from the router.
        
        Updates the internal position state from the latest router data.
        Note: Despite the None return type hint, this method returns the position value.
        """
        current_home_node = self._router.home_nodes.get(self._home_node.get("id"))
        if current_home_node.get("show_endpoints"):
            for end_point in current_home_node["show_endpoints"]:
                if end_point["id"] == self._get_state_endpoint_id:
                    self._position = end_point["value"]
        return self._position

    @property
    def is_closed(self):
        """
        @brief Check if the basic cover is closed.
        
        @return True if cover is closed, False otherwise.
        """
        return self._position

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the basic cover by activating the down endpoint.
        
        @param kwargs Additional keyword arguments (unused).
        @return None
        """
        try:
            await self._router._api.home.set_home_endpoint_value(
                self._home_node["id"], self._down_endpoint_id, {"value": True}
            )
        except InsufficientPermissionsError as err:
            _LOGGER.warning(
                "Home Assistant does not have permissions to modify the Freebox settings: %s", err
            )

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the basic cover by activating the up endpoint.
        
        @param kwargs Additional keyword arguments (unused).
        @return None
        """
        try:
            await self._router._api.home.set_home_endpoint_value(
                self._home_node["id"], self._up_endpoint_id, {"value": True}
            )
        except InsufficientPermissionsError as err:
            _LOGGER.warning(
                "Home Assistant does not have permissions to modify the Freebox settings: %s", err
            )

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the current basic cover movement.
        
        @param kwargs Additional keyword arguments (unused).
        @return None
        """
        try:
            await self._router._api.home.set_home_endpoint_value(
                self._home_node["id"], self._stop_endpoint_id, {"value": True}
            )
        except InsufficientPermissionsError as err:
            _LOGGER.warning(
                "Home Assistant does not have permissions to modify the Freebox settings: %s", err
            )
