"""
@file alarm_control_panel.py
@brief Support for Freebox alarm control panel entities.

This module provides alarm control panel functionality for Freebox Home devices,
allowing users to arm, disarm, and trigger alarms through Home Assistant.
"""
from __future__ import annotations

from typing import Any

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, FreeboxHomeCategory
from .entity import FreeboxHomeEntity
from .router import FreeboxRouter

##< Mapping from Freebox alarm states to Home Assistant alarm states
FREEBOX_TO_STATUS = {
    "alarm1_arming": AlarmControlPanelState.ARMING,
    "alarm2_arming": AlarmControlPanelState.ARMING,
    "alarm1_armed": AlarmControlPanelState.ARMED_AWAY,
    "alarm2_armed": AlarmControlPanelState.ARMED_HOME,
    "alarm1_alert_timer": AlarmControlPanelState.TRIGGERED,
    "alarm2_alert_timer": AlarmControlPanelState.TRIGGERED,
    "alert": AlarmControlPanelState.TRIGGERED,
    "idle": AlarmControlPanelState.DISARMED,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """
    @brief Set up Freebox alarm control panel entities from a config entry.
    
    Creates and registers alarm control panel entities for Freebox Home devices
    that have alarm capability.
    
    @param hass The Home Assistant instance
    @param entry The config entry for this integration
    @param async_add_entities Callback to add entities to Home Assistant
    @return None
    """
    router: FreeboxRouter = entry.runtime_data

    async_add_entities(
        (
            FreeboxAlarm(hass, router, home_node)
            for home_node in router.home_nodes.values()
            if home_node["category"] == FreeboxHomeCategory.ALARM
        ),
        True,
    )


class FreeboxAlarm(FreeboxHomeEntity, AlarmControlPanelEntity):
    """
    @brief Representation of a Freebox alarm control panel entity.
    
    This class implements an alarm control panel for Freebox Home devices,
    providing arm, disarm, and trigger functionality.
    """

    _attr_code_arm_required = False  ##< Code not required for arming/disarming

    def __init__(
        self, hass: HomeAssistant, router: FreeboxRouter, node: dict[str, Any]
    ) -> None:
        """
        @brief Initialize a Freebox alarm control panel entity.
        
        Sets up the alarm entity with command IDs for various alarm operations
        and configures supported features based on available commands.
        
        @param hass The Home Assistant instance
        @param router The FreeboxRouter instance
        @param node The node data from the Freebox API
        @return None
        """
        super().__init__(hass, router, node)

        # Commands
        self._command_trigger = self.get_command_id(
            node["type"]["endpoints"], "slot", "trigger"
        )
        self._command_arm_away = self.get_command_id(
            node["type"]["endpoints"], "slot", "alarm1"
        )
        self._command_arm_home = self.get_command_id(
            node["type"]["endpoints"], "slot", "alarm2"
        )
        self._command_disarm = self.get_command_id(
            node["type"]["endpoints"], "slot", "off"
        )
        self._command_state = self.get_command_id(
            node["type"]["endpoints"], "signal", "state"
        )

        self._attr_supported_features = (
            AlarmControlPanelEntityFeature.ARM_AWAY
            | (AlarmControlPanelEntityFeature.ARM_HOME if self._command_arm_home else 0)
            | AlarmControlPanelEntityFeature.TRIGGER
        )

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """
        @brief Send disarm command to the alarm.
        
        @param code Optional security code (not used for Freebox)
        @return None
        """
        await self.set_home_endpoint_value(self._command_disarm)

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """
        @brief Send arm away command to the alarm.
        
        @param code Optional security code (not used for Freebox)
        @return None
        """
        await self.set_home_endpoint_value(self._command_arm_away)

    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        """
        @brief Send arm home command to the alarm.
        
        @param code Optional security code (not used for Freebox)
        @return None
        """
        await self.set_home_endpoint_value(self._command_arm_home)

    async def async_alarm_trigger(self, code: str | None = None) -> None:
        """
        @brief Send alarm trigger command.
        
        @param code Optional security code (not used for Freebox)
        @return None
        """
        await self.set_home_endpoint_value(self._command_trigger)

    async def async_update(self) -> None:
        """
        @brief Update the alarm state from the Freebox API.
        
        Fetches the current alarm state and maps it to Home Assistant alarm state.
        
        @return None
        """
        state: str | None = await self.get_home_endpoint_value(self._command_state)
        if state:
            self._attr_alarm_state = FREEBOX_TO_STATUS.get(state)
        else:
            self._attr_alarm_state = None
