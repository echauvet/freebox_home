"""
@file alarm_control_panel.py
@author Freebox Home Contributors
@brief Support for Freebox alarm control panel entities.
@version 1.3.0

This module provides alarm control panel functionality for Freebox Home devices,
allowing users to arm, disarm, and trigger alarms through Home Assistant.

ALARM STATES EXPLAINED:
- DISARMED: Alarm is off, no monitoring
- ARMING: Countdown before alarm activates (time to leave)
- ARMED_AWAY: Full alarm mode (all sensors active)
- ARMED_HOME: Home mode (some sensors disabled, e.g., motion inside)
- TRIGGERED: Alarm is going off!

FREEBOX ALARM MODES:
- alarm1: Away mode (full protection)
- alarm2: Home mode (stay mode)
- off: Disarmed
"""
from __future__ import annotations

from datetime import timedelta
from typing import Any, Callable

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import dt as dt_util

from .const import DOMAIN, FreeboxHomeCategory, TEMP_REFRESH_DURATION, TEMP_REFRESH_INTERVAL, CONF_TEMP_REFRESH_INTERVAL, DEFAULT_TEMP_REFRESH_INTERVAL, CONF_TEMP_REFRESH_DURATION, DEFAULT_TEMP_REFRESH_DURATION
from .entity import FreeboxHomeEntity
from .router import FreeboxRouter

##< Mapping from Freebox alarm states to Home Assistant alarm states
# Freebox uses different state names than Home Assistant, so we translate them
# For example: Freebox "alarm1_armed" = Home Assistant "ARMED_AWAY"
FREEBOX_TO_STATUS = {
    "alarm1_arming": AlarmControlPanelState.ARMING,    # Countdown before away mode
    "alarm2_arming": AlarmControlPanelState.ARMING,    # Countdown before home mode
    "alarm1_armed": AlarmControlPanelState.ARMED_AWAY, # Away mode active
    "alarm2_armed": AlarmControlPanelState.ARMED_HOME, # Home mode active
    "alarm1_alert_timer": AlarmControlPanelState.TRIGGERED,  # Away alarm triggered
    "alarm2_alert_timer": AlarmControlPanelState.TRIGGERED,  # Home alarm triggered
    "alert": AlarmControlPanelState.TRIGGERED,         # General alarm triggered
    "idle": AlarmControlPanelState.DISARMED,           # Alarm off
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
    
    HOW IT WORKS:
    Scans all Freebox Home devices and creates an alarm entity for each
    device that has the "alarm" category.
    
    @param[in] hass Home Assistant instance coordinating the integration
    @param[in] entry Config entry providing router runtime data
    @param[in] async_add_entities Callback used to register entities with HA
    @return None
    @see FreeboxAlarm
    """
    router: FreeboxRouter = entry.runtime_data

    # Create alarm entities for all alarm-capable devices
    # This uses a "generator expression" to efficiently filter and create
    async_add_entities(
        (
            FreeboxAlarm(hass, router, home_node)
            for home_node in router.home_nodes.values()
            if home_node["category"] == FreeboxHomeCategory.ALARM
        ),
        True,  # Request update before adding
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
        
        COMMAND DISCOVERY:
        We search the device's endpoints to find the command IDs for:
        - trigger: Sound the alarm manually
        - alarm1: Arm in away mode (full protection)
        - alarm2: Arm in home mode (perimeter only)
        - off: Disarm the alarm
        - state: Read current alarm state
        
        @param[in] hass Home Assistant instance orchestrating updates
        @param[in] router FreeboxRouter instance managing API access
        @param[in] node Mapping containing Freebox Home node data
        @return None
        """
        super().__init__(hass, router, node)

        # Find the command IDs for each alarm operation
        # These are numeric IDs that we use to send commands to the Freebox
        self._command_trigger = self.get_command_id(
            node["type"]["endpoints"], "slot", "trigger"
        )
        self._command_arm_away = self.get_command_id(
            node["type"]["endpoints"], "slot", "alarm1"  # Away = alarm1
        )
        self._command_arm_home = self.get_command_id(
            node["type"]["endpoints"], "slot", "alarm2"  # Home = alarm2
        )
        self._command_disarm = self.get_command_id(
            node["type"]["endpoints"], "slot", "off"
        )
        self._command_state = self.get_command_id(
            node["type"]["endpoints"], "signal", "state"  # For reading status
        )

        # Tell Home Assistant which features this alarm supports
        # Always support: ARM_AWAY and TRIGGER
        # Optional: ARM_HOME (only if alarm2 command exists)
        self._attr_supported_features = (
            AlarmControlPanelEntityFeature.ARM_AWAY
            | (AlarmControlPanelEntityFeature.ARM_HOME if self._command_arm_home else 0)
            | AlarmControlPanelEntityFeature.TRIGGER
        )

    async def _start_temp_refresh(self) -> None:
        """
        Start fast polling after alarm commands.
        
        WHY FOR ALARMS?
        Alarm state changes can take a moment (e.g., arming countdown).
        We poll the Freebox API at a configurable interval for 120 seconds to show state transitions:
        DISARMED → ARMING → ARMED_AWAY
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
            await self.async_update()
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
        Clean up when alarm is removed from Home Assistant.
        
        Stop the fast polling timer to prevent errors.
        """
        self._router.stop_entity_refresh_timer(self.entity_id)

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """
        @brief Send disarm command to the alarm.
        
        Turns off the alarm. Called when user clicks "Disarm" in Home Assistant.
        
        @param[in] code Optional security code (unused by Freebox)
        @return None
        """
        # Cancel any existing refresh timer to start fresh
        self._router.stop_entity_refresh_timer(self.entity_id)
        
        await self.set_home_endpoint_value(self._command_disarm)
        # Get immediate state update
        await self.async_update()
        self.async_write_ha_state()
        # Start fast polling to show state change quickly
        await self._start_temp_refresh()

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """
        @brief Send arm away command to the alarm.
        
        Activates full alarm mode (all sensors). Called when user clicks
        "Arm Away" in Home Assistant. Good for when leaving home.
        
        @param[in] code Optional security code (unused by Freebox)
        @return None
        """
        # Cancel any existing refresh timer to start fresh
        self._router.stop_entity_refresh_timer(self.entity_id)
        
        await self.set_home_endpoint_value(self._command_arm_away)
        # Get immediate state update
        await self.async_update()
        self.async_write_ha_state()
        await self._start_temp_refresh()

    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        """
        @brief Send arm home command to the alarm.
        
        Activates home mode (perimeter sensors only, typically disables
        interior motion sensors). Good for when sleeping at home.
        
        @param[in] code Optional security code (unused by Freebox)
        @return None
        """
        # Cancel any existing refresh timer to start fresh
        self._router.stop_entity_refresh_timer(self.entity_id)
        
        await self.set_home_endpoint_value(self._command_arm_home)
        # Get immediate state update
        await self.async_update()
        self.async_write_ha_state()
        await self._start_temp_refresh()

    async def async_alarm_trigger(self, code: str | None = None) -> None:
        """
        @brief Send alarm trigger command.
        
        Manually triggers the alarm (sounds the siren). Use this for
        panic button functionality or testing.
        
        @param[in] code Optional security code (unused by Freebox)
        @return None
        """
        # Cancel any existing refresh timer to start fresh
        self._router.stop_entity_refresh_timer(self.entity_id)
        
        await self.set_home_endpoint_value(self._command_trigger)
        # Get immediate state update
        await self.async_update()
        self.async_write_ha_state()
        await self._start_temp_refresh()

    async def async_update(self) -> None:
        """
        @brief Update the alarm state from the Freebox API.
        
        Fetches the current alarm state from the Freebox and translates it
        to Home Assistant's alarm state format.
        
        For example: Freebox "alarm1_armed" becomes Home Assistant "ARMED_AWAY"
        
        @return None
        """
        # Get the raw state string from Freebox (e.g., "alarm1_armed")
        state: str | None = await self.get_home_endpoint_value(self._command_state)
        if state:
            # Translate to Home Assistant state using our mapping dictionary
            self._attr_alarm_state = FREEBOX_TO_STATUS.get(state)
        else:
            self._attr_alarm_state = None
