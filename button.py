"""
@file button.py
@brief Support for Freebox button entities.

This module provides button entity support for Freebox devices (Freebox v6 and Freebox mini 4K).
It implements reboot functionality as a button entity in Home Assistant.
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .router import FreeboxRouter


@dataclass
class FreeboxButtonRequiredKeysMixin:
    """
    @brief Mixin for required keys in Freebox button entities.
    
    This mixin defines the required callable for button press actions.
    """

    async_press: Callable[[FreeboxRouter], Awaitable]  ##< Async callable for button press action


@dataclass
class FreeboxButtonEntityDescription(
    ButtonEntityDescription, FreeboxButtonRequiredKeysMixin
):
    """
    @brief Entity description class for Freebox button entities.
    
    Combines ButtonEntityDescription with FreeboxButtonRequiredKeysMixin to provide
    complete button entity description for Freebox devices.
    """


BUTTON_DESCRIPTIONS: tuple[FreeboxButtonEntityDescription, ...] = (
    FreeboxButtonEntityDescription(
        key="reboot",
        name="Reboot Freebox",
        device_class=ButtonDeviceClass.RESTART,
        async_press=lambda router: router.reboot(),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """
    @brief Set up Freebox button entities from a config entry.
    
    Creates and registers button entities for the Freebox integration.
    
    @param hass The Home Assistant instance
    @param entry The config entry for this integration
    @param async_add_entities Callback to add entities to Home Assistant
    @return None
    """
    router: FreeboxRouter = hass.data[DOMAIN][entry.unique_id]
    entities = [
        FreeboxButton(router, description) for description in BUTTON_DESCRIPTIONS
    ]
    async_add_entities(entities, True)


class FreeboxButton(ButtonEntity):
    """
    @brief Representation of a Freebox button entity.
    
    This class implements button functionality for Freebox devices,
    allowing users to trigger actions like rebooting the device.
    """

    entity_description: FreeboxButtonEntityDescription  ##< Entity description for this button

    def __init__(
        self, router: FreeboxRouter, description: FreeboxButtonEntityDescription
    ) -> None:
        """
        @brief Initialize a Freebox button entity.
        
        @param router The FreeboxRouter instance
        @param description The button entity description
        @return None
        """
        self.entity_description = description
        self._router = router
        self._attr_unique_id = f"{router.mac} {description.name}"

    @property
    def device_info(self) -> DeviceInfo:
        """
        @brief Return the device information for this button.
        
        @return DeviceInfo object containing device details
        """
        return self._router.device_info

    async def async_press(self) -> None:
        """
        @brief Execute the button press action.
        
        Triggers the action associated with this button (e.g., rebooting the Freebox).
        
        @return None
        """
        await self.entity_description.async_press(self._router)
