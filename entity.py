"""
@file entity.py
@author Freebox Home Contributors
@brief Support for Freebox base entity features.
@version 1.2.0

This module provides the base entity class for all Freebox Home entities,
handling common functionality like device information, state updates, and
communication with the Freebox Home API.
"""

from __future__ import annotations

from collections.abc import Callable
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import CATEGORY_TO_MODEL, DOMAIN, FreeboxHomeCategory
from .router import FreeboxRouter

_LOGGER = logging.getLogger(__name__)


class FreeboxHomeEntity(Entity):
    """
    @brief Base representation of a Freebox Home entity.
    
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
        """
        @brief Initialize a Freebox Home entity.
        
        Sets up the entity with device information, manufacturer details,
        and configures the device registry entry.
        
        @param hass The Home Assistant instance
        @param router The FreeboxRouter instance
        @param node The main node data from the Freebox API
        @param sub_node Optional sub-node data for multi-endpoint devices
        @return None
        """
        self._hass = hass
        self._router = router
        self._node = node
        self._sub_node = sub_node
        self._id = node["id"]
        self._attr_name = node["label"].strip()
        self._device_name = self._attr_name
        self._attr_unique_id = f"{self._router.mac}-node_{self._id}"

        if sub_node is not None:
            self._attr_name += " " + sub_node["label"].strip()
            self._attr_unique_id += "-" + sub_node["name"].strip()

        self._available = True
        self._firmware = node["props"].get("FwVersion")
        self._manufacturer = "Freebox SAS"
        self._remove_signal_update: Callable[[], None] | None = None

        self._model = CATEGORY_TO_MODEL.get(node["category"])
        if self._model is None:
            if node["type"].get("inherit") == "node::rts":
                self._manufacturer = "Somfy"
                self._model = CATEGORY_TO_MODEL[FreeboxHomeCategory.RTS]
            elif node["type"].get("inherit") == "node::ios":
                self._manufacturer = "Somfy"
                self._model = CATEGORY_TO_MODEL[FreeboxHomeCategory.IOHOME]

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._id)},
            manufacturer=self._manufacturer,
            model=self._model,
            name=self._device_name,
            sw_version=self._firmware,
            via_device=(
                DOMAIN,
                router.mac,
            ),
        )

    async def async_update_signal(self) -> None:
        """
        @brief Update entity state from router signal.

        Called when the router dispatches an update signal to refresh
        entity state and attributes from the latest node data. Updates
        the node reference, adjusts the human-readable name (including
        sub-node label when present), and pushes the new state to Home Assistant.

        @return None
        @see FreeboxRouter.signal_home_device_update
        """
        self._node = self._router.home_nodes[self._id]
        # Update name
        if self._sub_node is None:
            self._attr_name = self._node["label"].strip()
        else:
            self._attr_name = (
                self._node["label"].strip() + " " + self._sub_node["label"].strip()
            )
        self.async_write_ha_state()

    async def set_home_endpoint_value(
        self, command_id: int | None, value: bool | None = None
    ) -> bool:
        """
        @brief Set a Home endpoint value via the Freebox API.

        Sends a command to the Freebox Home API to set a value for
        a specific endpoint on this device. Used for operations such as
        arming alarms or toggling actuators.

        @param[in] command_id Endpoint command identifier to execute
        @param[in] value Optional payload value to send (defaults to None)
        @return True on success, False when command_id is missing
        @throw freebox_api.exceptions.FreepyboxError Derivatives on API failure
        @see get_home_endpoint_value
        """
        if command_id is None:
            _LOGGER.error("Unable to SET a value through the API. Command is None")
            return False

        await self._router.home.set_home_endpoint_value(
            self._id, command_id, {"value": value}
        )
        return True

    async def get_home_endpoint_value(self, command_id: Any) -> Any | None:
        """
        @brief Get a Home endpoint value via the Freebox API.

        Retrieves the current value for a specific endpoint on this device
        from the Freebox Home API. Useful for reading sensors and status flags.

        @param[in] command_id Endpoint command identifier to read
        @return Endpoint value when available, None if command_id is invalid
        @throw freebox_api.exceptions.FreepyboxError Derivatives on API failure
        @see set_home_endpoint_value
        """
        if command_id is None:
            _LOGGER.error("Unable to GET a value through the API. Command is None")
            return None

        node = await self._router.home.get_home_endpoint_value(self._id, command_id)
        return node.get("value")

    def get_command_id(self, nodes, ep_type: str, name: str) -> int | None:
        """
        @brief Get the command ID for a specific endpoint.

        Searches through the node's endpoints to find the command identifier
        matching the requested endpoint type and name.

        @param[in] nodes Iterable of endpoint node definitions
        @param[in] ep_type Endpoint type discriminator (for example "slot" or "signal")
        @param[in] name Endpoint name to search for
        @return Matching command identifier or None when not found
        @warning Logs a warning when the mapping cannot be resolved
        """
        node = next(
            filter(lambda x: (x["name"] == name and x["ep_type"] == ep_type), nodes),
            None,
        )
        if not node:
            _LOGGER.warning(
                "The Freebox Home device has no command value for: %s/%s", name, ep_type
            )
            return None
        return node["id"]

    async def async_added_to_hass(self) -> None:
        """
        @brief Register state update callback when entity is added to Home Assistant.
        
        Connects to the router's device update signal to receive notifications
        when the device state changes.
        
        @return None
        """
        self.remove_signal_update(
            async_dispatcher_connect(
                self._hass,
                self._router.signal_home_device_update,
                self.async_update_signal,
            )
        )

    async def async_will_remove_from_hass(self) -> None:
        """
        @brief Clean up when entity is removed from Home Assistant.
        
        Disconnects from the router's device update signal.
        
        @return None
        """
        if self._remove_signal_update is not None:
            self._remove_signal_update()

    def remove_signal_update(self, dispatcher: Callable[[], None]) -> None:
        """
        @brief Register state update callback dispatcher.
        
        Stores the dispatcher callback for later cleanup.
        
        @param dispatcher The dispatcher callback function
        @return None
        """
        self._remove_signal_update = dispatcher

    def get_value(self, ep_type: str, name: str) -> Any:
        """
        @brief Get a value from the node's show_endpoints.
        
        Searches through the node's visible endpoints to find and return
        the value matching the specified endpoint type and name.
        
        @param ep_type The endpoint type
        @param name The endpoint name
        @return The endpoint value if found, None otherwise
        """
        node = next(
            (
                endpoint
                for endpoint in self._node["show_endpoints"]
                if endpoint["name"] == name and endpoint["ep_type"] == ep_type
            ),
            None,
        )
        if node is None:
            _LOGGER.warning(
                "The Freebox Home device has no node value for: %s/%s", ep_type, name
            )
            return None
        return node.get("value")