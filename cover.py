"""
@file cover.py
@author Freebox Home Contributors
@brief Support for Freebox Cover entities.
@version 1.2.0.1

This module provides Home Assistant cover platform integration for Freebox home automation devices,
including shutters, openers, and basic shutters. It handles position control and state management
for motorized covers connected to the Freebox home automation system.

COVER TYPES EXPLAINED:
- Shutter: Full position control (0-100%), like electric blinds
- Opener: Full position control for gates or garage doors  
- Basic Shutter: Simple up/down/stop control without position feedback (binary open/closed)

KEY CONCEPTS:
- Position: 0 = fully closed, 100 = fully open
- Freebox uses inverted scale internally (100 = closed), so we flip it for Home Assistant
- After sending commands, we poll the Freebox API every 2 seconds for 120 seconds to show real-time progress
"""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any, Callable

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
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DOMAIN, HOME_NODES_COVERS, TEMP_REFRESH_DURATION, TEMP_REFRESH_INTERVAL, CONF_TEMP_REFRESH_INTERVAL, DEFAULT_TEMP_REFRESH_INTERVAL, CONF_TEMP_REFRESH_DURATION, DEFAULT_TEMP_REFRESH_DURATION
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
    
    WHY DIFFERENT CLASSES?
    - Shutters and openers have precise position control (0-100%)
    - Basic shutters only have up/down/stop (no position feedback)
    So we use different entity classes with different capabilities.

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

    # Loop through all devices and find the covers
    for home_node in router.home_nodes.values():
        # Full position control covers (shutters and openers)
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
        # Simple binary covers (basic shutters)
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
        # Cache endpoint IDs for efficient access
        self._get_endpoint_id = None
        self._set_endpoint_id = None
        self._stop_endpoint_id = None
        
        # Discover set/get endpoints once during initialization
        for endpoint in home_node.get("show_endpoints", []):
            ep_name = endpoint.get("name")
            ep_type = endpoint.get("ep_type")
            ep_id = endpoint.get("id")
            
            if ep_name == "position_set":
                if ep_type == "signal":
                    self._get_endpoint_id = ep_id
                elif ep_type == "slot":
                    self._set_endpoint_id = ep_id
            elif ep_name == "stop" and ep_type == "slot":
                self._stop_endpoint_id = ep_id

    @property
    def device_info(self) -> DeviceInfo:
        """
        @brief Return the device information for this home node cover.
        
        @return DeviceInfo object with manufacturer, model, firmware version, etc.
        """
        return DeviceInfo(
            identifiers={(DOMAIN, self._home_node["id"])},
            model=self._home_node["category"],
            name=self._home_node["label"],
            sw_version=self._home_node.get("props", {}).get("FwVersion"),
            via_device=(DOMAIN, self._router.mac),
            manufacturer="Freebox SAS",
        )

    @callback
    def async_update_state(self) -> bool:
        """
        @brief Refresh the cover position and state from the router.
        
        Updates the internal position state from the latest router data.
        
        @return True if the cover is closed (position == 0), False otherwise
        """
        current_home_node = self._router.home_nodes.get(self._home_node["id"])
        if current_home_node and self._get_endpoint_id:
            for end_point in current_home_node.get("show_endpoints", []):
                if end_point.get("id") == self._get_endpoint_id:
                    self._position = 100 - end_point.get("value", 0)
                    break
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
        
        POSITION INVERSION:
        Home Assistant uses 0=closed, 100=open
        Freebox uses 0=open, 100=closed (opposite!)
        So we convert: (100 - position) before sending to Freebox

        @param[in] position Target position from 0 (closed) to 100 (open)
        @return None
        """
        # Convert Home Assistant position to Freebox position
        value_position = {"value": (100 - position)}
        try:
            await self._router._api.home.set_home_endpoint_value(
                self._home_node["id"], self._set_endpoint_id, value_position
            )
            # Start fast polling to show movement progress
            await self._start_temp_refresh()
        except InsufficientPermissionsError as err:
            _LOGGER.warning(
                "Home Assistant does not have permissions to modify the Freebox settings: %s", err
            )

    async def get_position(self) -> int | None:
        """
        @brief Get the current cover position from the API.
        
        Fetches the complete node data (more efficient than single endpoint call)
        and extracts the position value, converting it to Home Assistant's scale.

        @return Integer position value from 0 (closed) to 100 (open)
        """
        try:
            # Get complete node data (all endpoints) in one API call
            node_data = await self._router.get_node_data(self._home_node["id"])
            if node_data and "show_endpoints" in node_data:
                # Find the position endpoint in the node data
                for endpoint in node_data["show_endpoints"]:
                    if endpoint["id"] == self._get_endpoint_id:
                        # Convert Freebox position (0=open, 100=closed) to HA (0=closed, 100=open)
                        self._position = 100 - endpoint["value"]
                        break
        except InsufficientPermissionsError as err:
            _LOGGER.warning(
                "Home Assistant does not have permissions to read Freebox settings: %s", err
            )
        except Exception as err:
            _LOGGER.error(
                "Unexpected error getting cover position for %s: %s",
                self._attr_name,
                err,
            )
        return self._position

    async def async_close_cover(self, **kwargs: Any) -> None:
        """
        @brief Close the cover completely.
        
        This is a convenience method that sets position to 0 (fully closed).
        Called when user clicks "Close" button in Home Assistant.

        @param[in] kwargs Additional keyword arguments (unused)
        @return None
        """
        self._router.stop_entity_refresh_timer(self.entity_id)
        
        # Optimistically set position for immediate UI feedback
        self._position = 0
        self.async_write_ha_state()
        
        await self.set_position(0)
        await self.get_position()
        self.async_write_ha_state()

    async def _start_temp_refresh(self) -> None:
        """
        Start fast polling after position changes.
        
        WHY WE NEED THIS:
        When a shutter is moving, it takes time (10-30 seconds typically).
        We want to show the real-time position in Home Assistant's UI,
        so we poll the Freebox API at configurable intervals for a configurable duration after any command.
        After that, we stop to avoid unnecessary API calls.
        """
        # Check if entity is properly initialized
        if not self.entity_id:
            _LOGGER.warning("Cannot start temp refresh for %s: entity_id not set", self._attr_name)
            return
        
        # Get the configured refresh interval and duration
        refresh_interval = self._router.config_entry.options.get(
            CONF_TEMP_REFRESH_INTERVAL, DEFAULT_TEMP_REFRESH_INTERVAL
        )
        refresh_duration = self._router.config_entry.options.get(
            CONF_TEMP_REFRESH_DURATION, DEFAULT_TEMP_REFRESH_DURATION
        )
        
        _LOGGER.debug("Starting temp refresh for %s (interval=%ss, duration=%ss)", 
                     self.entity_id, refresh_interval, refresh_duration)
        
        # Create refresh callback
        async def _refresh() -> None:
            await self.get_position()
            self.async_write_ha_state()
        
        # Use global timer system
        self._router.start_entity_refresh_timer(
            entity_id=self.entity_id,
            refresh_callback=_refresh,
            interval_seconds=refresh_interval,
            duration_seconds=refresh_duration,
        )

    async def async_will_remove_from_hass(self) -> None:
        """
        Clean up when cover is removed from Home Assistant.
        
        Stop the fast polling timer if it's running to prevent errors
        and memory leaks.
        """
        self._router.stop_entity_refresh_timer(self.entity_id)

    async def async_open_cover(self, **kwargs: Any) -> None:
        """
        @brief Open the cover completely.

        @param[in] kwargs Additional keyword arguments (unused)
        @return None
        """
        self._router.stop_entity_refresh_timer(self.entity_id)
        
        # Optimistically set position for immediate UI feedback
        self._position = 100
        self.async_write_ha_state()
        
        await self.set_position(100)
        await self.get_position()
        self.async_write_ha_state()

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """
        @brief Set the cover to a specific position.

        @param[in] kwargs Keyword arguments containing ATTR_POSITION with target position
        @return None
        """
        target_position = kwargs.get(ATTR_POSITION)
        if target_position is None:
            return
            
        self._router.stop_entity_refresh_timer(self.entity_id)
        
        # Optimistically set position for immediate UI feedback
        self._position = target_position
        self.async_write_ha_state()
        
        await self.set_position(target_position)
        await self.get_position()
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
            # Update position after stopping to reflect where it actually stopped
            await self.get_position()
            self.async_write_ha_state()
        except InsufficientPermissionsError as err:
            _LOGGER.warning(
                "Home Assistant does not have permissions to modify Freebox settings: %s", err
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
        # Cache endpoint IDs for efficient access
        self._get_state_endpoint_id = None
        self._stop_endpoint_id = None
        self._up_endpoint_id = None
        self._down_endpoint_id = None
        
        # Discover set/get endpoints once during initialization
        for endpoint in home_node.get("show_endpoints", []):
            ep_name = endpoint.get("name")
            ep_type = endpoint.get("ep_type")
            ep_id = endpoint.get("id")
            
            if ep_name == "state" and ep_type == "signal":
                self._get_state_endpoint_id = ep_id
            elif ep_type == "slot":
                if ep_name == "stop":
                    self._stop_endpoint_id = ep_id
                elif ep_name == "up":
                    self._up_endpoint_id = ep_id
                elif ep_name == "down":
                    self._down_endpoint_id = ep_id

    @property
    def device_info(self) -> DeviceInfo:
        """
        @brief Return the device information for this basic cover.
        
        @return DeviceInfo object with manufacturer, model, firmware version, etc.
        """
        return DeviceInfo(
            identifiers={(DOMAIN, self._home_node["id"])},
            model=self._home_node["category"],
            name=self._home_node["label"],
            sw_version=self._home_node.get("props", {}).get("FwVersion"),
            via_device=(DOMAIN, self._router.mac),
            manufacturer="Freebox SAS",
        )

    @callback
    def async_update_state(self) -> Any:
        """
        @brief Refresh the binary state (open/closed) from the router.
        
        Updates the internal position state from the latest router data.
        
        @return The position value from the endpoint
        """
        current_home_node = self._router.home_nodes.get(self._home_node["id"])
        if current_home_node and self._get_state_endpoint_id:
            for end_point in current_home_node.get("show_endpoints", []):
                if end_point.get("id") == self._get_state_endpoint_id:
                    self._position = end_point.get("value")
                    break
        return self._position

    @property
    def is_closed(self) -> bool | None:
        """
        @brief Check if the basic cover is closed.
        
        @return True if cover is closed, False if open, None if unknown
        """
        if self._position is None:
            return None
        return bool(self._position)

    async def get_state(self) -> bool | None:
        """
        @brief Get the current cover state from the API.

        @return Boolean state value (True if closed, False if open)
        """
        try:
            # Get complete node data (all endpoints) in one API call
            node_data = await self._router.get_node_data(self._home_node["id"])
            if node_data and "show_endpoints" in node_data:
                # Find the state endpoint in the node data
                for endpoint in node_data["show_endpoints"]:
                    if endpoint["id"] == self._get_state_endpoint_id:
                        self._position = endpoint["value"]
                        break
        except InsufficientPermissionsError as err:
            _LOGGER.warning(
                "Home Assistant does not have permissions to read Freebox settings: %s", err
            )
        except Exception as err:
            _LOGGER.error(
                "Unexpected error getting cover state for %s: %s",
                self._attr_name,
                err,
            )
        return self._position

    async def _start_temp_refresh(self) -> None:
        """Increase refresh frequency for TEMP_REFRESH_DURATION after a movement command."""
        # Check if entity is properly initialized
        if not self.entity_id:
            _LOGGER.warning("Cannot start temp refresh for %s: entity_id not set", self._attr_name)
            return
        
        # Get the configured refresh interval and duration
        refresh_interval = self._router.config_entry.options.get(
            CONF_TEMP_REFRESH_INTERVAL, DEFAULT_TEMP_REFRESH_INTERVAL
        )
        refresh_duration = self._router.config_entry.options.get(
            CONF_TEMP_REFRESH_DURATION, DEFAULT_TEMP_REFRESH_DURATION
        )
        
        _LOGGER.debug("Starting temp refresh for %s (interval=%ss, duration=%ss)", 
                     self.entity_id, refresh_interval, refresh_duration)
        
        # Create refresh callback
        async def _refresh() -> None:
            await self.get_state()
            self.async_write_ha_state()
        
        # Use global timer system
        self._router.start_entity_refresh_timer(
            entity_id=self.entity_id,
            refresh_callback=_refresh,
            interval_seconds=refresh_interval,
            duration_seconds=refresh_duration,
        )

    async def async_will_remove_from_hass(self) -> None:
        """Clean up refresh timer when entity is removed."""
        self._router.stop_entity_refresh_timer(self.entity_id)

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the basic cover by activating the down endpoint.
        
        @param kwargs Additional keyword arguments (unused).
        @return None
        """
        # Cancel any existing refresh timer to start fresh
        self._router.stop_entity_refresh_timer(self.entity_id)
        
        try:
            await self._router._api.home.set_home_endpoint_value(
                self._home_node["id"], self._down_endpoint_id, {"value": True}
            )
            # Immediately fetch state to show movement has started
            await self.get_state()
            self.async_write_ha_state()
            await self._start_temp_refresh()
        except InsufficientPermissionsError as err:
            _LOGGER.warning(
                "Home Assistant does not have permissions to modify Freebox settings: %s", err
            )

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the basic cover by activating the up endpoint.
        
        @param kwargs Additional keyword arguments (unused).
        @return None
        """
        # Cancel any existing refresh timer to start fresh
        self._router.stop_entity_refresh_timer(self.entity_id)
        
        try:
            await self._router._api.home.set_home_endpoint_value(
                self._home_node["id"], self._up_endpoint_id, {"value": True}
            )
            # Immediately fetch state to show movement has started
            await self.get_state()
            self.async_write_ha_state()
            await self._start_temp_refresh()
        except InsufficientPermissionsError as err:
            _LOGGER.warning(
                "Home Assistant does not have permissions to modify Freebox settings: %s", err
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
            # Update state after stopping to reflect where it actually stopped
            await self.get_state()
            self.async_write_ha_state()
        except InsufficientPermissionsError as err:
            _LOGGER.warning(
                "Home Assistant does not have permissions to modify Freebox settings: %s", err
            )
