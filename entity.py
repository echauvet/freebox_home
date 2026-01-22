"""Think of this as a "template" or "parent class" that all specific Freebox
devices (covers, switches, alarms, etc.) inherit from. It handles all the
common tasks so individual device types don't have to repeat the same code.

Utility Features:
- Safe string truncation for long device names
- Timestamp formatting for sensor displays
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import dt as dt_util

from .const import (
    CATEGORY_TO_MODEL,
    CONF_TEMP_REFRESH_INTERVAL,
    DEFAULT_TEMP_REFRESH_INTERVAL,
    DOMAIN,
    FreeboxHomeCategory,
    TEMP_REFRESH_DURATION,
    TEMP_REFRESH_INTERVAL,
)
from .router import FreeboxRouter
from .utilities import truncate_string, format_timestamp

_LOGGER = logging.getLogger(__name__)


class FreeboxHomeEntity(Entity):
    """ Base representation of a Freebox Home entity.
    
    This class provides common functionality for all Freebox Home entities,
    including device information, state management, and API communication.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        router: FreeboxRouter,
        node: dict[str, Any],
        sub_node: dict[str, Any] | None = None,
    ) -> None:
        """ Initialize a Freebox Home entity.
        
        Sets up the entity with device information, manufacturer details,
        and configures the device registry entry.
        Args:
            hass: The Home Assistant instance
        Args:
            router: The FreeboxRouter instance
        Args:
            node: The main node data from the Freebox API
        Args:
            sub_node: Optional sub-node data for multi-endpoint devices
        Returns:
            None
        """
        # Store references to Home Assistant and the router
        self._hass = hass
        self._router = router
        
        # Store the device node data (contains all device info from Freebox)
        self._node = node
        self._sub_node = sub_node
        
        # Extract basic device information
        self._id = node["id"]  # Unique ID from Freebox
        self._attr_name = truncate_string(node["label"].strip(), max_length=100)  # Device name (safe truncation)
        self._device_name = self._attr_name
        
        # Create a unique ID for Home Assistant (combines router MAC + device ID)
        self._attr_unique_id = f"{self._router.mac}-node_{self._id}"

        # If this is a sub-device (e.g., button on a multi-button remote),
        # append the sub-device name to make it unique
        if sub_node is not None:
            self._attr_name += " " + truncate_string(sub_node["label"].strip(), max_length=50)
            self._attr_unique_id += "-" + sub_node["name"].strip()

        # Set entity availability and firmware version
        self._available = True
        self._firmware = node["props"].get("FwVersion")
        
        # This will hold the cleanup function for update signals
        self._remove_signal_update: Callable[[], None] | None = None

        # Determine manufacturer and model based on device category
        # Most devices are made by Freebox, but some (like Somfy shutters)
        # are third-party devices that work with Freebox
        self._model = CATEGORY_TO_MODEL.get(node["category"])
        node_inherit = node["type"].get("inherit")
        
        # Check if this is a Somfy RTS (Radio Technology Somfy) device
        if node_inherit == "node::rts":
            self._manufacturer = "Somfy"
            self._model = CATEGORY_TO_MODEL[FreeboxHomeCategory.RTS]
        # Check if this is a Somfy IO-homecontrol device
        elif node_inherit == "node::ios":
            self._manufacturer = "Somfy"
            self._model = CATEGORY_TO_MODEL[FreeboxHomeCategory.IOHOME]
        # Default to Freebox for all other devices
        else:
            self._manufacturer = "Freebox SAS"

        # Create device information for Home Assistant's device registry
        # This groups all entities from the same physical device together in the UI
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._id)},  # Unique identifier for this device
            manufacturer=self._manufacturer,     # Who made it (Freebox, Somfy, etc.)
            model=self._model,                   # What type of device it is
            name=self._device_name,              # Human-readable name
            sw_version=self._firmware,           # Firmware version
            via_device=(                         # Connected through the Freebox router
                DOMAIN,
                router.mac,
            ),
        )

    async def async_update_signal(self) -> None:
        """ Update entity state from router signal.

        Called when the router dispatches an update signal to refresh
        entity state and attributes from the latest node data. Updates
        the node reference, adjusts the human-readable name (including
        sub-node label when present), and pushes the new state to Home Assistant.
        
        This is called automatically when the Freebox sends us new data about
        this device (push notification), so we don't have to constantly ask
        for updates (polling).
        Returns:
            None
        See Also:
            FreeboxRouter.signal_home_device_update
        """
        # Get the latest device data from the router's cache
        self._node = self._router.home_nodes[self._id]
        
        # Update the display name (user might have renamed it in Freebox app)
        if self._sub_node is None:
            self._attr_name = self._node["label"].strip()
        else:
            self._attr_name = (
                self._node["label"].strip() + " " + self._sub_node["label"].strip()
            )
        
        # Tell Home Assistant to update the UI with the new state
        self.async_write_ha_state()

    async def set_home_endpoint_value(
        self, command_id: int | None, value: bool | None = None
    ) -> bool:
        """ Set a Home endpoint value via the Freebox API.

        Sends a command to the Freebox Home API to set a value for
        a specific endpoint on this device. Used for operations such as
        arming alarms or toggling actuators.
        
        Example: To turn on a switch, we send a command to its "on" endpoint.
        Example: To set an alarm to "armed away", we send a command to its "arm_away" endpoint.
        Args:
            command_id: Endpoint command identifier to execute
        Args:
            value: Optional payload value to send (defaults to None)
        Returns:
            True on success, False when command_id is missing
        Raises:
            freebox_api.exceptions.FreepyboxError Derivatives on API failure
        See Also:
            get_home_endpoint_value
        """
        # Validate that we have a valid command ID
        if command_id is None:
            _LOGGER.error("Cannot set endpoint value: command_id is None")
            return False

        # Send the command to the Freebox
        await self._router.home.set_home_endpoint_value(
            self._id, command_id, {"value": value}
        )
        return True

    async def get_home_endpoint_value(self, command_id: Any) -> Any | None:
        """ Get a Home endpoint value via the Freebox API.

        Retrieves the current value for a specific endpoint on this device
        by fetching the complete node data (more efficient than single endpoint call).
        
        Example: To check if a switch is on, we read its "state" endpoint.
        Example: To check alarm status, we read its "status" endpoint.
        Args:
            command_id: Endpoint command identifier to read
        Returns:
            Endpoint value when available, None if command_id is invalid
        Raises:
            freebox_api.exceptions.FreepyboxError Derivatives on API failure
        See Also:
            set_home_endpoint_value
        """
        # Validate that we have a valid command ID
        if command_id is None:
            _LOGGER.error("Cannot get endpoint value: command_id is None")
            return None

        # Get complete node data (all endpoints) in one API call
        node_data = await self._router.get_node_data(self._id)
        if node_data and "show_endpoints" in node_data:
            # Find the requested endpoint in the node data
            for endpoint in node_data["show_endpoints"]:
                if endpoint["id"] == command_id:
                    return endpoint.get("value")
        return None

    async def _start_temp_refresh(self) -> None:
        """ Start temporary high-frequency refresh after state change.
        
        Initiates a temporary polling period with high frequency (configurable interval)
        for 120 seconds after a state-changing command using the global timer system.
        
        WHY WE NEED THIS:
        When you close a shutter, it takes time to physically close. We want to
        show the real-time progress in Home Assistant, so we poll more frequently
        for a short period. After 120 seconds, we return to normal update frequency.
        Returns:
            None
        """
        # Get the configured refresh interval (default to 2 seconds if not set)
        refresh_interval = self._router.config_entry.options.get(
            CONF_TEMP_REFRESH_INTERVAL, DEFAULT_TEMP_REFRESH_INTERVAL
        )
        
        # Create refresh callback
        async def _refresh() -> None:
            await self.async_update()
            self.async_write_ha_state()
        
        # Use global timer system
        self._router.start_entity_refresh_timer(
            entity_id=self.entity_id,
            refresh_callback=_refresh,
            interval_seconds=refresh_interval,
            duration_seconds=TEMP_REFRESH_DURATION,
        )

    def get_command_id(self, nodes: list[dict[str, Any]], ep_type: str, name: str) -> int | None:
        """ Get the command ID for a specific endpoint.

        Searches through the node's endpoints to find the command identifier
        matching the requested endpoint type and name.
        
        WHAT ARE ENDPOINTS?
        Each Freebox device has multiple "endpoints" - think of them as buttons
        or sensors on the device. For example, a shutter has endpoints for:
        - "position_set" (to set the position)
        - "stop" (to stop movement)
        - "state" (to read current position)
        
        This function finds the numeric ID for a specific endpoint by name.
        Args:
            nodes: Iterable of endpoint node definitions
        Args:
            ep_type: Endpoint type discriminator (for example "slot" or "signal")
        Args:
            name: Endpoint name to search for
        Returns:
            Matching command identifier or None when not found
        @warning Logs a warning when the mapping cannot be resolved
        """
        # Search through all endpoints to find the one we want
        # This uses a "generator expression" - an efficient way to search a list
        endpoint = next(
            (
                node
                for node in nodes
                if node["name"] == name and node["ep_type"] == ep_type
            ),
            None,  # Return None if not found
        )
        
        # If we didn't find it, log a warning
        if endpoint is None:
            _LOGGER.warning(
                "Freebox Home device has no command for %s/%s", name, ep_type
            )
            return None
        
        # Return the numeric ID of this endpoint
        return endpoint["id"]

    async def async_added_to_hass(self) -> None:
        """ Register state update callback when entity is added to Home Assistant.
        
        Connects to the router's device update signal to receive notifications
        when the device state changes.
        
        LIFECYCLE METHOD:
        Home Assistant calls this automatically when the entity is first loaded.
        We use it to "subscribe" to updates from the Freebox - like subscribing
        to a newsletter so we get notifications when something changes.
        Returns:
            None
        """
        # Connect to the router's update signal so we get notified of changes
        # The remove_signal_update() stores the cleanup function for later
        self.remove_signal_update(
            async_dispatcher_connect(
                self._hass,
                self._router.signal_home_device_update,
                self.async_update_signal,  # Call this function when updates arrive
            )
        )

    async def async_will_remove_from_hass(self) -> None:
        """ Clean up when entity is removed from Home Assistant.
        
        Disconnects from the router's device update signal and stops any active refresh timer.
        
        LIFECYCLE METHOD:
        Home Assistant calls this when the entity is being removed (e.g., integration
        is unloaded or disabled). We need to clean up our timers and subscriptions
        to avoid memory leaks and prevent errors from trying to update a deleted entity.
        Returns:
            None
        """
        # Stop any active refresh timer using global system
        self._router.stop_entity_refresh_timer(self.entity_id)
        
        # Disconnect from the router's update signal
        if self._remove_signal_update is not None:
            self._remove_signal_update()  # Unsubscribe from updates

    def remove_signal_update(self, dispatcher: Callable[[], None]) -> None:
        """ Register state update callback dispatcher.
        
        Stores the dispatcher callback for later cleanup.
        
        This is a helper that stores the "unsubscribe" function so we can
        call it later when cleaning up.
        Args:
            dispatcher: The dispatcher callback function
        Returns:
            None
        """
        self._remove_signal_update = dispatcher

    def get_value(self, ep_type: str, name: str) -> Any:
        """ Get a value from the node's show_endpoints.
        
        Searches through the node's visible endpoints to find and return
        the value matching the specified endpoint type and name.
        
        DIFFERENCE FROM get_home_endpoint_value():
        This method reads from cached data (no API call), while
        get_home_endpoint_value() makes a fresh API request to the Freebox.
        Use this when you just need the last known value quickly.
        Args:
            ep_type: The endpoint type
        Args:
            name: The endpoint name
        Returns:
            The endpoint value if found, None otherwise
        """
        # Search through the cached endpoint data
        endpoint = next(
            (
                ep
                for ep in self._node["show_endpoints"]
                if ep["name"] == name and ep["ep_type"] == ep_type
            ),
            None,
        )
        
        if endpoint is None:
            _LOGGER.warning(
                "Freebox Home device has no value for %s/%s", ep_type, name
            )
            return None
        
        return endpoint.get("value")
