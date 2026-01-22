"""Freebox cover platform for shutters, openers, and blinds.

Supports position-controlled covers (0-100%) and binary covers (up/down/stop).
Automatic fast polling after commands with 20s auto-stop when stable.
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
from .entity_refresh_manager import EntityRefreshManager
from .router import FreeboxRouter

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Freebox cover entities from a config entry.
    
    Discovers shutters, openers, and basic shutters from home nodes.
    Uses different entity classes based on position control capability.
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
    """Base class for Freebox cover entities with common functionality.
    
    This abstract base class provides:
    - EntityRefreshManager integration for temporary fast polling
    - Abstract methods for value fetching and tracking
    - Common lifecycle management (added/removed from Home Assistant)
    - Refresh timer management with automatic cleanup
    
    Child classes must implement:
    - get_current_value(): Fetch current position/state from API
    - get_tracked_value(): Return value to track for change detection
    
    Refresh behavior:
    - 2-second polling interval (configurable)
    - 20-second auto-stop on no change
    - 60-second maximum duration
    - Stop and restart on each action
    """

    _attr_should_poll = False

    def __init__(
        self,
        router: FreeboxRouter,
        description: CoverEntityDescription,
        unik: Any,
    ) -> None:
        """Initialize Freebox cover entity.
        
        Creates EntityRefreshManager with 20-second no-change timeout.
        The refresh manager handles temporary fast polling when cover moves.
        
        Args:
            router: FreeboxRouter instance for API access and timer management
            description: Cover entity description with metadata
            unik: Unique identifier for this specific cover instance
        """
        self.entity_description = description
        self._router = router
        self._unik = unik
        self._attr_unique_id = f"{router.mac} {description.name} {unik}"
        
        # Create refresh manager instance (20s no-change timeout for covers)
        self._refresh_manager = EntityRefreshManager(router, f"{description.name} {unik}", no_change_timeout=20)

    @callback
    def async_update_state(self) -> None:
        """Update cover state. Implemented by subclasses."""

    async def get_current_value(self) -> Any:
        """Get current value (position/state). Must be implemented by subclasses."""
        raise NotImplementedError

    def get_tracked_value(self) -> Any:
        """Get the value to track for changes. Must be implemented by subclasses."""
        raise NotImplementedError

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return self._router.device_info

    @callback
    def async_on_demand_update(self) -> None:
        """Handle on-demand state updates."""
        self.async_update_state()
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Register state update callback and set entity ID for refresh manager."""
        self.async_update_state()
        
        # Set entity ID in refresh manager once available
        self._refresh_manager.set_entity_id(self.entity_id)
        
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                self._router.signal_sensor_update,
                self.async_on_demand_update,
            )
        )

    async def _start_temp_refresh(self) -> None:
        """Start fast polling after movement command.
        
        Delegates to EntityRefreshManager which:
        - Fetches initial value before starting timer
        - Polls at configured interval (default 2s)
        - Tracks value changes via get_tracked_value()
        - Auto-stops after 20s of no change
        - Stops after 60s maximum duration
        
        The refresh manager was already stopped before this call
        in cover action methods (set_position, open, close, stop).
        """
        await self._refresh_manager.start_refresh(
            get_value_callback=self.get_current_value,
            get_tracked_value_callback=self.get_tracked_value,
            write_state_callback=self.async_write_ha_state,
        )

    async def async_will_remove_from_hass(self) -> None:
        """Clean up timers when entity is removed.
        
        Ensures refresh timer is properly stopped when entity is removed
        from Home Assistant (e.g., integration reload, device removal).
        """
        self._refresh_manager.stop_refresh()


class FreeboxHomeNodeCover(FreeboxCover):
    """Freebox cover with position control (shutters, openers).
    
    Supports covers with full position control (0-100%):
    - Shutters: Window/door shutters
    - Openers: Gates, garage doors
    
    Features:
    - SET_POSITION: Set to specific position (0-100%)
    - OPEN: Fully open (position 100)
    - CLOSE: Fully close (position 0)
    - STOP: Stop movement at current position
    
    Position handling:
    - Home Assistant: 0=closed, 100=open
    - Freebox API: 0=open, 100=closed (inverted)
    - Automatic conversion in set_position()
    
    Refresh behavior:
    - Triggers on any position change command
    - Tracks position changes every 2 seconds
    - Stops when position stable for 20 seconds
    - Each action restarts timer with clean state
    """

    def __init__(
        self,
        router: FreeboxRouter,
        home_node: dict[str, Any],
        description: CoverEntityDescription,
    ) -> None:
        """Initialize position-controlled cover entity.
        
        Discovers endpoint IDs from home_node for:
        - position_set (signal): Get current position
        - position_set (slot): Set target position
        - stop (slot): Stop movement command
        
        Args:
            router: FreeboxRouter instance for API access
            home_node: Freebox home node data dict
            description: Entity description with key/name
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

        self._position = None
        self._get_endpoint_id = None
        self._set_endpoint_id = None
        self._stop_endpoint_id = None
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
        """Return device information for this cover."""
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
        """Refresh cover position from router data.
        
        Called during fast polling to update position from cached data.
        Inverts Freebox scale (0=open, 100=closed) to HA scale (0=closed, 100=open).
        
        Returns:
            True if cover is fully closed (position == 0)
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
        """Return current position (0-100)."""
        return self._position

    @property
    def is_closed(self):
        """Return True if cover is fully closed."""
        return self._position == 0

    async def set_position(self, position: int) -> None:
        """Set cover position. Converts HA scale (0=closed) to Freebox scale (100=closed).
        
        Stops any existing refresh timer and starts new fast polling to track
        the cover movement in real-time.
        
        Args:
            position: Target position in Home Assistant scale (0-100)
                     0 = fully closed, 100 = fully open
        """
        # Convert Home Assistant position to Freebox position
        value_position = {"value": (100 - position)}
        try:
            await self._router._api.home.set_home_endpoint_value(
                self._home_node["id"], self._set_endpoint_id, value_position
            )
            # Stop any existing refresh and start new fast polling to show movement progress
            self._refresh_manager.stop_refresh()
            await self._start_temp_refresh()
        except InsufficientPermissionsError as err:
            _LOGGER.warning(
                "Home Assistant does not have permissions to modify the Freebox settings: %s", err
            )

    async def get_position(self) -> int | None:
        """Get current position from API and convert to HA scale."""
        try:
            node_data = await self._router.get_node_data(self._home_node["id"])
            if node_data and "show_endpoints" in node_data:
                for endpoint in node_data["show_endpoints"]:
                    if endpoint["id"] == self._get_endpoint_id:
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
        """Close cover to position 0 (fully closed).
        
        Stops any existing refresh timer and starts new fast polling
        to track the cover closing in real-time.
        """
        await self.async_set_cover_position(position=0)
        
    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open cover to position 100 (fully open).
        
        Stops any existing refresh timer and starts new fast polling
        to track the cover opening in real-time.
        """
        await self.async_set_cover_position(position=100)

    async def get_current_value(self) -> int | None:
        """Get current position from API.
        
        Called by EntityRefreshManager during fast polling.
        Fetches the latest position from Freebox API.
        
        Returns:
            Current position (0-100) or None if unavailable
        """
        return await self.get_position()

    def get_tracked_value(self) -> int | None:
        """Get position value for tracking changes.
        
        Called by EntityRefreshManager to detect when position changes.
        If this value doesn't change for 20 seconds, refresh auto-stops.
        
        Returns:
            Current position value (0-100) or None
        """
        return self._position

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Set cover to specific position."""
        target_position = kwargs.get(ATTR_POSITION)
        if target_position is None:
            return
        self._position = target_position
        self.async_write_ha_state()
        
        await self.set_position(target_position)
        await self.get_position()
        self.async_write_ha_state()

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop cover movement at current position.
        
        Sends stop command to Freebox API and restarts fast polling
        to capture the final position after deceleration.
        """
        try:
            await self._router._api.home.set_home_endpoint_value(
                self._home_node["id"], self._stop_endpoint_id, {"value": True}
            )
            await self.get_position()
            self.async_write_ha_state()
            # Stop any existing refresh and restart to capture final position
            self._refresh_manager.stop_refresh()
            await self._start_temp_refresh()
        except InsufficientPermissionsError as err:
            _LOGGER.warning(
                "Home Assistant does not have permissions to modify Freebox settings: %s", err
            )


class FreeboxHomeNodeBasicCover(FreeboxCover):
    """Freebox cover with basic binary control (open/close/stop only).
    
    Supports covers without position feedback:
    - Gates: Binary open/close gates
    - Simple openers: Basic door/window openers
    
    Features:
    - OPEN: Send up command
    - CLOSE: Send down command
    - STOP: Stop movement
    - No position control (binary state only)
    
    State handling:
    - Tracks binary state from 'state' endpoint
    - No position feedback (0-100%)
    - Detects state changes during movement
    
    Refresh behavior:
    - Triggers on open/close/stop commands
    - Tracks state changes every 2 seconds
    - Stops when state stable for 20 seconds
    - Each action restarts timer with clean state
    """

    def __init__(
        self,
        router: FreeboxRouter,
        home_node: dict[str, Any],
        description: CoverEntityDescription,
    ) -> None:
        """Initialize binary cover entity.
        
        Discovers endpoint IDs from home_node for:
        - state (signal): Get current binary state
        - up (slot): Send open command
        - down (slot): Send close command
        - stop (slot): Stop movement command
        
        Args:
            router: FreeboxRouter instance for API access
            home_node: Freebox home node data dict
            description: Entity description with key/name
        """
        super().__init__(router, description, home_node["id"])
        self._home_node = home_node
        self._attr_name = f"{home_node['label']} {description.name}"
        self._unique_id = (
            f"{self._router.mac} {description.key} {self._home_node['id']}"
        )
        self._attr_supported_features = CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP

        self._position = None
        self._get_state_endpoint_id = None
        self._stop_endpoint_id = None
        self._up_endpoint_id = None
        self._down_endpoint_id = None
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
        """Return device information for this cover."""
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
        """Refresh binary state from router data.
        
        Called during fast polling to update state from cached data.
        Tracks binary state value (not 0-100% position).
        
        Returns:
            Current state value or None
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
        """Return True if cover is closed."""
        if self._position is None:
            return None
        return bool(self._position)

    async def get_state(self) -> bool | None:
        """Get current binary state from API.
        
        Fetches state from Freebox API and updates _position.
        Unlike position-based covers, this returns binary state.
        
        Returns:
            Binary state value or None if unavailable
        """
        try:
            node_data = await self._router.get_node_data(self._home_node["id"])
            if node_data and "show_endpoints" in node_data:
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

    async def get_current_value(self) -> bool | None:
        """Get current state from API.
        
        Called by EntityRefreshManager during fast polling.
        Delegates to get_state() to fetch latest binary state.
        
        Returns:
            Binary state value or None
        """
        return await self.get_state()

    def get_tracked_value(self) -> bool | None:
        """Get state value for tracking changes.
        
        Called by EntityRefreshManager to detect when state changes.
        If this value doesn't change for 20 seconds, refresh auto-stops.
        
        Returns:
            Current state value or None
        """
        return self._position

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Send close (down) command to cover.
        
        Stops any existing refresh timer and starts new fast polling
        to track state changes during closing.
        """
        try:
            await self._router._api.home.set_home_endpoint_value(
                self._home_node["id"], self._down_endpoint_id, {"value": True}
            )
            await self.get_state()
            self.async_write_ha_state()
            # Stop any existing refresh and start new one
            self._refresh_manager.stop_refresh()
            await self._start_temp_refresh()
        except InsufficientPermissionsError as err:
            _LOGGER.warning(
                "Home Assistant does not have permissions to modify Freebox settings: %s", err
            )

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Send open (up) command to cover.
        
        Stops any existing refresh timer and starts new fast polling
        to track state changes during opening.
        """
        try:
            await self._router._api.home.set_home_endpoint_value(
                self._home_node["id"], self._up_endpoint_id, {"value": True}
            )
            await self.get_state()
            self.async_write_ha_state()
            # Stop any existing refresh and start new one
            self._refresh_manager.stop_refresh()
            await self._start_temp_refresh()
        except InsufficientPermissionsError as err:
            _LOGGER.warning(
                "Home Assistant does not have permissions to modify Freebox settings: %s", err
            )
      
    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop cover movement at current position.
        
        Sends stop command to Freebox API and restarts fast polling
        to capture the final state after stopping.
        """
        try:
            await self._router._api.home.set_home_endpoint_value(
                self._home_node["id"], self._stop_endpoint_id, {"value": True}
            )
            await self.get_state()
            self.async_write_ha_state()
            # Stop any existing refresh and restart to capture final state
            self._refresh_manager.stop_refresh()
            await self._start_temp_refresh()
        except InsufficientPermissionsError as err:
            _LOGGER.warning(
                "Home Assistant does not have permissions to modify Freebox settings: %s", err
            )
