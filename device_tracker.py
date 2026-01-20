"""
@file device_tracker.py
@author Freebox Home Contributors
@brief Device tracker component for Freebox devices.
@version 1.2.0.1

This module provides device tracking functionality for Freebox routers,
supporting Freebox v6 and Freebox mini 4K. It monitors connected devices
on the network and reports their connection status to Home Assistant.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.device_tracker import SourceType
from homeassistant.components.device_tracker.config_entry import ScannerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DEFAULT_DEVICE_NAME, DEVICE_ICONS, DOMAIN
from .router import FreeboxRouter


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """
    @brief Set up device tracker for Freebox component.

    Initializes the device tracker platform for a Freebox router config entry.
    Registers a dispatcher callback to automatically add new entities when the
    router discovers devices on the network.

    @param[in] hass Home Assistant instance coordinating the integration
    @param[in] entry Config entry providing router runtime data
    @param[in] async_add_entities Callback used to register new entities with HA
    @return None
    @see add_entities
    """
    router: FreeboxRouter = entry.runtime_data
    tracked: set[str] = set()

    @callback
    def update_router() -> None:
        """
        @brief React to router discovery updates.

        Callback function invoked by dispatcher when the router publishes
        discovery events. It delegates to add_entities so newly detected devices
        become available as tracker entities.

        @return None
        @see router.signal_device_new
        """
        add_entities(router, async_add_entities, tracked)

    entry.async_on_unload(
        async_dispatcher_connect(hass, router.signal_device_new, update_router)
    )

    update_router()


@callback
def add_entities(
    router: FreeboxRouter, async_add_entities: AddEntitiesCallback, tracked: set[str]
) -> None:
    """
    @brief Add new tracker entities from the router.

    Creates FreeboxDevice entities for devices discovered by the router
    that are not already tracked. Maintains a set of MAC addresses to
    prevent duplicate entity creation.

    @param[in] router FreeboxRouter instance providing device metadata
    @param[in] async_add_entities Callback to register entities with Home Assistant
    @param[in,out] tracked Mutable set of MAC addresses already tracked
    @return None
    """
    new_tracked = []

    for mac, device in router.devices.items():
        if mac in tracked:
            continue

        new_tracked.append(FreeboxDevice(router, device))
        tracked.add(mac)

    async_add_entities(new_tracked, True)


class FreeboxDevice(ScannerEntity):
    """
    @brief Representation of a Freebox device.
    
    This class represents a device connected to a Freebox router. It tracks
    the device's connection state, MAC address, and other attributes. Updates
    are pushed via dispatcher signals rather than polling.
    """

    _attr_should_poll = False  ##< Disable polling; updates are pushed via dispatcher

    def __init__(self, router: FreeboxRouter, device: dict[str, Any]) -> None:
        """
        @brief Initialize a Freebox device tracker entity.

        Sets up the entity with identification, manufacturer metadata, and
        default attributes drawn from the router's device list.

        @param[in] router FreeboxRouter instance managing this device
        @param[in] device Mapping describing the Freebox host
        @return None
        """
        self._router = router
        self._name = device["primary_name"].strip() or DEFAULT_DEVICE_NAME
        self._mac = device["l2ident"]["id"]
        self._manufacturer = device["vendor_name"]
        self._icon = icon_for_freebox_device(device)
        self._active = False
        self._attrs: dict[str, Any] = {}

    @callback
    def async_update_state(self) -> None:
        """
        @brief Update the Freebox device state.

        Refreshes the device's connection flag and auxiliary attributes from
        the router's latest topology snapshot. For routers, uses custom attrs;
        for standard devices, converts epoch timestamps to datetime objects.

        @return None
        """
        device = self._router.devices[self._mac]
        self._active = device["active"]
        if device.get("attrs") is None:
            # device
            self._attrs = {
                "last_time_reachable": datetime.fromtimestamp(
                    device["last_time_reachable"]
                ),
                "last_time_activity": datetime.fromtimestamp(device["last_activity"]),
            }
        else:
            # router
            self._attrs = device["attrs"]

    @property
    def mac_address(self) -> str:
        """
        @brief Return a unique ID.
        
        @return The MAC address of the device
        """
        return self._mac

    @property
    def name(self) -> str:
        """
        @brief Return the name.
        
        @return The friendly name of the device
        """
        return self._name

    @property
    def is_connected(self) -> bool:
        """
        @brief Return true if the device is connected to the network.
        
        @return True if the device is currently active/connected, False otherwise
        """
        return self._active

    @property
    def source_type(self) -> SourceType:
        """
        @brief Return the source type.
        
        @return SourceType.ROUTER indicating this is a router-based device tracker
        """
        return SourceType.ROUTER

    @property
    def icon(self) -> str:
        """
        @brief Return the icon.
        
        @return The Material Design Icon identifier for this device
        """
        return self._icon

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """
        @brief Return the attributes.
        
        @return Dictionary of additional state attributes for this device
        """
        return self._attrs

    @callback
    def async_on_demand_update(self) -> None:
        """
        @brief Update state on demand.
        
        Callback triggered by dispatcher signals when device state changes.
        Updates internal state and writes the new state to Home Assistant.
        
        @return None
        """
        self.async_update_state()
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """
        @brief Register state update callback.
        
        Called when the entity is added to Home Assistant. Performs initial state
        update and registers a dispatcher callback for future updates.
        
        @return None
        """
        self.async_update_state()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                self._router.signal_device_update,
                self.async_on_demand_update,
            )
        )


def icon_for_freebox_device(device) -> str:
    """
    @brief Return a device icon from its type.

    Maps the Freebox device host_type to an appropriate Material Design Icon.
    Falls back to a generic network help icon if the device type is unknown.

    @param[in] device Mapping containing host metadata with a 'host_type' key
    @return Material Design Icon identifier string
    """
    return DEVICE_ICONS.get(device["host_type"], "mdi:help-network")
