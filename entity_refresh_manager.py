"""Generic refresh manager for entities with temporary fast polling.

Provides fast refresh with auto-stop after 20s of no change or 60s maximum.
Usable for covers, lights, switches, or any entity requiring movement tracking.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Callable, TYPE_CHECKING

from homeassistant.util import dt as dt_util

from .const import (
    CONF_TEMP_REFRESH_INTERVAL,
    DEFAULT_TEMP_REFRESH_INTERVAL,
    CONF_TEMP_REFRESH_DURATION,
    DEFAULT_TEMP_REFRESH_DURATION,
)

if TYPE_CHECKING:
    from .router import FreeboxRouter

_LOGGER = logging.getLogger(__name__)


class EntityRefreshManager:
    """Manages temporary fast refresh for entities with auto-stop on no movement.
    
    Generic refresh manager suitable for any entity type that:
    - Changes state during an operation (covers moving, lights transitioning, etc.)
    - Needs fast polling to track progress
    - Should stop polling when movement/change completes
    
    Features:
    - Configurable refresh interval (default: 2 seconds)
    - Configurable maximum duration (default: 60 seconds, capped)
    - Auto-stops after 20 seconds of no change
    - Error handling to prevent crashes
    - Supports any value type through callbacks
    """

    def __init__(self, router: FreeboxRouter, entity_name: str, no_change_timeout: int = 20) -> None:
        """Initialize the refresh manager.
        
        Args:
            router: FreeboxRouter instance for timer management
            entity_name: Name of the entity for logging
            no_change_timeout: Seconds to wait before stopping if no change detected (default: 20)
        """
        self._router = router
        self._entity_name = entity_name
        self._entity_id: str | None = None
        self._last_value: Any = None
        self._last_value_change: datetime | None = None
        self._no_change_timeout = no_change_timeout

    def set_entity_id(self, entity_id: str) -> None:
        """Set the entity ID once it's available."""
        self._entity_id = entity_id

    async def start_refresh(
        self,
        get_value_callback: Callable[[], Any],
        get_tracked_value_callback: Callable[[], Any],
        write_state_callback: Callable[[], None],
        interval: int | None = None,
        duration: int | None = None,
        max_duration: int = 60,
    ) -> None:
        """Start fast polling with auto-stop on no movement.
        
        Args:
            get_value_callback: Async function to fetch current value from API
            get_tracked_value_callback: Function to get the value to track for changes
            write_state_callback: Function to write state to Home Assistant
            interval: Refresh interval in seconds (uses config default if None)
            duration: Maximum refresh duration in seconds (uses config default if None)
            max_duration: Absolute maximum duration in seconds (default: 60)
        """
        # Check if entity is properly initialized
        if not self._entity_id:
            _LOGGER.warning("Cannot start temp refresh for %s: entity_id not set", self._entity_name)
            return
        
        # Always cancel any existing timer before starting a new one
        self._router.stop_entity_refresh_timer(self._entity_id)
        
        # Get the configured refresh interval and duration
        if interval is None:
            interval = self._router.config_entry.options.get(
                CONF_TEMP_REFRESH_INTERVAL, DEFAULT_TEMP_REFRESH_INTERVAL
            )
        if duration is None:
            duration = self._router.config_entry.options.get(
                CONF_TEMP_REFRESH_DURATION, DEFAULT_TEMP_REFRESH_DURATION
            )
        
        # Cap duration to specified maximum
        duration = min(duration, max_duration)
        
        _LOGGER.debug("Starting temp refresh for %s (interval=%ss, duration=%ss, timeout=%ss)", 
                     self._entity_id, interval, duration, self._no_change_timeout)
        
        # Get initial value before starting timer
        await get_value_callback()
        
        # Reset tracking variables
        self._last_value = get_tracked_value_callback()
        self._last_value_change = dt_util.utcnow()
        
        # Create refresh callback with auto-stop on no movement
        async def _refresh() -> None:
            try:
                await get_value_callback()
                write_state_callback()
                
                current_value = get_tracked_value_callback()
                
                # Check if value has changed (handle None values)
                if current_value is not None and current_value != self._last_value:
                    self._last_value = current_value
                    self._last_value_change = dt_util.utcnow()
                elif self._last_value_change and current_value is not None:
                    # Value hasn't changed - check if timeout elapsed
                    time_since_change = (dt_util.utcnow() - self._last_value_change).total_seconds()
                    if time_since_change >= self._no_change_timeout:
                        _LOGGER.debug("Entity %s not changing for %ss, stopping fast refresh", 
                                     self._entity_id, self._no_change_timeout)
                        self.stop_refresh()
            except Exception as err:
                _LOGGER.error("Error in refresh callback for %s: %s", self._entity_id, err)
                # Don't stop timer on errors, let it continue or expire naturally
        
        # Use global timer system
        self._router.start_entity_refresh_timer(
            entity_id=self._entity_id,
            refresh_callback=_refresh,
            interval_seconds=interval,
            duration_seconds=duration,
        )

    def stop_refresh(self) -> None:
        """Stop the active refresh timer."""
        if self._entity_id:
            self._router.stop_entity_refresh_timer(self._entity_id)


# Backward compatibility alias for existing imports
CoverRefreshManager = EntityRefreshManager
