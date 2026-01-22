"""Freebox switch platform for WiFi, call alerts, and home automation.

Controls WiFi state and home automation device switches.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any

from freebox_api.exceptions import InsufficientPermissionsError

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    TEMP_REFRESH_DURATION,
    TEMP_REFRESH_INTERVAL,
    CONF_TEMP_REFRESH_INTERVAL,
    DEFAULT_TEMP_REFRESH_INTERVAL,
    CONF_TEMP_REFRESH_DURATION,
    DEFAULT_TEMP_REFRESH_DURATION,
)
from .router import FreeboxRouter

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """ Set up the Freebox switch entities.
    
    Discovers all switches: the WiFi toggle plus any smart home devices
    (like smart plugs) that have switch-type endpoints.
    
    HOW IT WORKS:
    1. Always add a WiFi switch (to control router's WiFi)
    2. Loop through all home automation devices
    3. Find any that have boolean "slot" endpoints (these are switches)
    4. Skip shutters (they're covers, not switches)
        Args:
            hass: Home Assistant instance coordinating the integration
        Args:
            entry: Config entry providing router runtime data
        Args:
            async_add_entities: Callback used to register entities with HA
        Returns:
            None
        See Also:
            FreeboxHomeNodeSwitch
        See Also:
            FreeboxWifiSwitch
    """
    router: FreeboxRouter = entry.runtime_data

    entities = []

    # Always add the WiFi control switch
    entities.append(FreeboxWifiSwitch(router))

    _LOGGER.info(
        "%s - %s - %s home node(s)", router.name, router.mac, len(router.home_nodes)
    )

    # Find all home automation switches
    for home_node in router.home_nodes.values():
        # Skip shutters (they're handled by cover.py)
        if home_node["category"] != "shutter":
            # Look for switch-type endpoints (boolean slots)
            for endpoint in home_node.get("show_endpoints"):
                if endpoint["ep_type"] == "slot" and endpoint["value_type"] == "bool":
                    # Found a switch! Add it to our list
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
    """ Representation of a Freebox switch.
    
    Base class for Freebox switch entities with common functionality.
    """

    _attr_should_poll = False

    def __init__(
        self,
        router: FreeboxRouter,
        endpoint_name: str,
        unik: Any,
    ) -> None:
        """ Initialize a Freebox switch.
        Args:
            router: FreeboxRouter instance managing API access
        Args:
            endpoint_name: Name of the endpoint represented by this switch
        Args:
            unik: Unique identifier component for the switch
        Returns:
            None
        """
        self.entity_description = SwitchEntityDescription(
            key="switch", name=endpoint_name
        )
        self._router = router
        self._unik = unik
        self._attr_unique_id = f"{router.mac} {endpoint_name} {unik}"

    @callback
    def async_update_state(self) -> None:
        """ Update the Freebox switch state.
        
        Placeholder for subclasses to populate the on/off state from router data.
        Returns:
            None
        """
        # state = self._router.sensors[self.entity_description.key]
        # self._attr_is_on = state

    @property
    def device_info(self) -> DeviceInfo:
        """ Return the device information.
        Returns:
            DeviceInfo object containing device details
        """
        return self._router.device_info

    @callback
    def async_on_demand_update(self) -> None:
        """ Update state on demand.
        
        Called when dispatcher signals a state change. Refreshes the state and
        pushes it to Home Assistant.
        Returns:
            None
        """
        self.async_update_state()
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Register state update callback.
        
        Called when entity is added to Home Assistant.
        Returns:
            None
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
    """ Representation of a Freebox Home node switch.
    
    Switch entity for controlling Freebox home automation nodes.
    """

    def __init__(
        self,
        router: FreeboxRouter,
        home_node: dict[str, Any],
        endpoint: dict[str, Any],
        description: SwitchEntityDescription,
    ) -> None:
        """ Initialize a Freebox Home node switch.
        Args:
            router: FreeboxRouter instance managing API access
        Args:
            home_node: Mapping containing home node information
        Args:
            endpoint: Mapping containing endpoint information
        Args:
            description: Switch entity description metadata
        Returns:
            None
        """
        super().__init__(router, description, f"{home_node['id']} {endpoint['id']}")
        self._home_node = home_node
        self._endpoint = endpoint
        self._attr_name = f"{home_node['label']} {endpoint['name']}"
        self._unique_id = f"{self._router.mac} {endpoint['name']} {self._home_node['id']} {endpoint['id']}"
        self._enabled = None
        self._get_endpoint_id = None

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
        """ Return the device information.
        Returns:
            DeviceInfo object containing device details including firmware version.
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
        """ Return true if device is on.
        Returns:
            True if the switch is on, False otherwise.
        """
        return self._enabled

    @callback
    def async_update_state(self) -> None:
        """ Update the Freebox Home node switch state.
        
        Reads the latest endpoint value from the router snapshot and synchronizes
        the entity attributes, ensuring Home Assistant reflects the real device state.
        Returns:
            None
        """
        current_home_node = self._router.home_nodes.get(self._home_node.get("id"))
        if current_home_node.get("show_endpoints"):
            for end_point in current_home_node["show_endpoints"]:
                if self._get_endpoint_id == end_point["id"]:
                    self._enabled = end_point["value"]
                    break
        self._attr_is_on = self._enabled

    async def get_state(self) -> bool | None:
        """ Get the current switch state from the API.
        
        Fetches the complete node data (more efficient) and extracts the switch state.
        Unlike covers, switches are simple: True = on, False = off.
        Returns:
            Boolean state value (True if on, False if off)
        """
        try:
            # Get complete node data (all endpoints) in one API call
            node_data = await self._router.get_node_data(self._home_node["id"])
            if node_data and "show_endpoints" in node_data:
                # Find the state endpoint in the node data
                for endpoint in node_data["show_endpoints"]:
                    if endpoint["id"] == self._get_endpoint_id:
                        self._enabled = endpoint["value"]
                        self._attr_is_on = self._enabled
                        break
        except InsufficientPermissionsError as err:
            _LOGGER.warning(
                "Home Assistant does not have permissions to read Freebox settings: %s", err
            )
        except Exception as err:
            _LOGGER.error(
                "Unexpected error getting switch state for %s: %s",
                self._attr_name,
                err,
            )
        return self._enabled

    async def _start_temp_refresh(self) -> None:
        """
        Start fast polling after state changes.
        
        WHY FOR SWITCHES?
        Even though switches are simpler than covers (just on/off),
        the physical device might take a moment to respond.
        We poll the Freebox API at a configurable interval for 120 seconds to quickly show the real state.
        """
        # Get the configured refresh interval and duration
        refresh_interval = self._router.config_entry.options.get(
            CONF_TEMP_REFRESH_INTERVAL, DEFAULT_TEMP_REFRESH_INTERVAL
        )
        refresh_duration = self._router.config_entry.options.get(
            CONF_TEMP_REFRESH_DURATION, DEFAULT_TEMP_REFRESH_DURATION
        )
        
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
        """
        Clean up when switch is removed from Home Assistant.
        
        Stop the fast polling timer if it's running.
        """
        self._router.stop_entity_refresh_timer(self.entity_id)

    async def _async_set_state(self, enabled: bool) -> None:
        """ Turn the switch on or off.
        
        Sends the command to the Freebox to change the switch state.
        Then starts fast polling to quickly reflect the actual state change.
        Args:
            enabled: True to enable, False to disable the endpoint
        Returns:
            None
        """
        # Prepare the command payload
        value_enabled = {"value": enabled}
        try:
            # Send the command to the Freebox
            await self._router._api.home.set_home_endpoint_value(
                self._home_node["id"], self._endpoint["id"], value_enabled
            )
            # Optimistically update our local state
            self._enabled = enabled
            # Start fast polling to confirm the change
            await self._start_temp_refresh()
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
        """ Turn the switch on.
        Args:
            kwargs: Additional keyword arguments (unused)
        Returns:
            None
        """
        # Cancel any existing refresh timer to start fresh
        self._router.stop_entity_refresh_timer(self.entity_id)
        
        await self._async_set_state(True)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """ Turn the switch off.
        Args:
            kwargs: Additional keyword arguments (unused)
        Returns:
            None
        """
        # Cancel any existing refresh timer to start fresh
        self._router.stop_entity_refresh_timer(self.entity_id)
        
        await self._async_set_state(False)
        self.async_write_ha_state()

    async def async_update(self) -> None:
        """Update the entity state.
        
        Note: This is a lifecycle method and should not return a value.
        """
        # async_update should just update internal state, not return


class FreeboxWifiSwitch(SwitchEntity):
    """ Representation of a Freebox WiFi switch.

    Switch entity for controlling the Freebox router WiFi functionality.
    """

    def __init__(self, router: FreeboxRouter) -> None:
        """ Initialize the WiFi switch entity.
        Args:
            router: FreeboxRouter instance managing API access
        Returns:
            None
        """
        self._name = "Freebox WiFi"
        self._state: bool | None = None
        self._router = router
        self._unique_id = f"{self._router.mac} {self._name}"

    @property
    def unique_id(self) -> str:
        """ Return a unique ID.
        Returns:
            Unique identifier string for the entity.
        """
        return self._unique_id

    @property
    def name(self) -> str:
        """ Return the name of the switch.
        Returns:
            The switch entity name.
        """
        return self._name

    @property
    def is_on(self) -> bool | None:
        """ Return true if device is on.
        Returns:
            True if WiFi is on, False if off, None if unknown.
        """
        return self._state

    @property
    def device_info(self) -> DeviceInfo:
        """ Return the device information.
        Returns:
            DeviceInfo object containing device details.
        """
        return self._router.device_info

    async def _async_set_state(self, enabled: bool) -> None:
        """ Turn the WiFi switch on or off.
        Args:
            enabled: True to enable WiFi, False to disable
        Returns:
            None
        """
        wifi_config = {"enabled": enabled}
        try:
            await self._router.wifi.set_global_config(wifi_config)
        except InsufficientPermissionsError as err:
            _LOGGER.warning(
                "Home Assistant does not have permissions to modify WiFi settings: %s", err
            )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """ Turn the WiFi switch on.
        Args:
            kwargs: Additional keyword arguments (unused)
        Returns:
            None
        """
        # Cancel any existing refresh timer to start fresh
        self._router.stop_entity_refresh_timer(self.entity_id)
        
        await self._async_set_state(True)
        # Get immediate state confirmation
        await self.async_update()
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """ Turn the WiFi switch off.
        Args:
            kwargs: Additional keyword arguments (unused)
        Returns:
            None
        """
        # Cancel any existing refresh timer to start fresh
        self._router.stop_entity_refresh_timer(self.entity_id)
        
        await self._async_set_state(False)
        # Get immediate state confirmation
        await self.async_update()
        self.async_write_ha_state()

    async def async_update(self) -> None:
        """Get the state and update it.
        
        Fetches the current WiFi state from the router.
        Returns:
            None
        """
        datas = await self._router.wifi.get_global_config()
        active = datas["enabled"]
        self._state = bool(active)
