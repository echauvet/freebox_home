""""""
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
    """ Mixin for required keys in Freebox button entities.
    
    This mixin defines the required callable for button press actions.
    """

    async_press: Callable[[FreeboxRouter], Awaitable]  ##< Async callable for button press action


@dataclass
class FreeboxButtonEntityDescription(
    ButtonEntityDescription, FreeboxButtonRequiredKeysMixin
):
    """ Entity description class for Freebox button entities.
    
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
    """ Set up Freebox button entities from a config entry.
    
    Creates and registers button entities for the Freebox integration.
        Args:
            hass: Home Assistant instance coordinating the integration
        Args:
            entry: Config entry providing router runtime data
        Args:
            async_add_entities: Callback used to register entities with HA
        Returns:
            None
        See Also:
            FreeboxButton
    """
    router: FreeboxRouter = entry.runtime_data
    entities = [
        FreeboxButton(router, description) for description in BUTTON_DESCRIPTIONS
    ]
    async_add_entities(entities, True)


class FreeboxButton(ButtonEntity):
    """ Representation of a Freebox button entity.
    
    This class implements button functionality for Freebox devices,
    allowing users to trigger actions like rebooting the device.
    """

    entity_description: FreeboxButtonEntityDescription  ##< Entity description for this button

    def __init__(
        self, router: FreeboxRouter, description: FreeboxButtonEntityDescription
    ) -> None:
        """ Initialize a Freebox button entity.
        Args:
            router: FreeboxRouter instance managing API access
        Args:
            description: Button entity description metadata
        Returns:
            None
        """
        self.entity_description = description
        self._router = router
        self._attr_unique_id = f"{router.mac} {description.name}"

    @property
    def device_info(self) -> DeviceInfo:
        """ Return the device information for this button.
        Returns:
            DeviceInfo object containing device details
        """
        return self._router.device_info

    async def async_press(self) -> None:
        """ Execute the button press action.

        Triggers the action associated with this button (e.g., rebooting the Freebox).
        Returns:
            None
        """
        await self.entity_description.async_press(self._router)
