"""Configuration validation helpers for safe operational bounds.

Validates scan intervals, reboot schedules, refresh timings, and network settings
to ensure values fall within supported ranges.
"""
from __future__ import annotations

import re
from typing import Any


def validate_scan_interval(value: Any) -> int:
    """ Validate normal polling scan interval.
    
    Ensures the polling interval is within safe bounds to prevent
    API overload while maintaining responsiveness.
        Args:
            value: Value to validate (int or convertible)
        Returns:
            Validated interval in seconds
        Raises:
            ValueError if value is out of range
        See Also:
            DEFAULT_SCAN_INTERVAL
    """
    try:
        interval = int(value)
        if not (10 <= interval <= 300):
            raise ValueError(f"Scan interval must be 10-300 seconds, got {interval}")
        return interval
    except (ValueError, TypeError) as err:
        raise ValueError(f"Invalid scan interval: {err}") from err


def validate_reboot_interval(value: Any) -> int:
    """ Validate scheduled reboot interval.
    
    Ensures reboot frequency is reasonable (0 disables, 1-30 enables).
        Args:
            value: Value to validate (int or convertible)
        Returns:
            Validated interval in days
        Raises:
            ValueError if value is out of range
        See Also:
            DEFAULT_REBOOT_INTERVAL_DAYS
    """
    try:
        interval = int(value)
        if not (0 <= interval <= 30):
            raise ValueError(f"Reboot interval must be 0-30 days, got {interval}")
        return interval
    except (ValueError, TypeError) as err:
        raise ValueError(f"Invalid reboot interval: {err}") from err


def validate_reboot_time(value: str) -> str:
    """ Validate scheduled reboot time format.
    
    Ensures time is in valid 24-hour HH:MM format.
        Args:
            value: Time string to validate
        Returns:
            Validated time string (HH:MM)
        Raises:
            ValueError if format is invalid
        Note:
            Valid formats: "00:00" to "23:59"
    """
    if not isinstance(value, str):
        raise ValueError(f"Reboot time must be string, got {type(value).__name__}")
    
    if not re.match(r"^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$", value.strip()):
        raise ValueError(
            f"Reboot time must be in HH:MM format (24-hour), got '{value}'"
        )
    return value.strip()


def validate_temp_refresh_interval(value: Any) -> int:
    """ Validate fast polling interval (temporary refresh rate).
    
    Ensures temporary polling frequency is high enough for responsiveness
    while not overwhelming the API with requests during time-sensitive operations
    like cover position updates and action feedback.
    
    FAST POLLING INTERVAL (1-5 seconds):
    - Used when cover position updates or actions are triggered
    - Provides rapid feedback to user without excessive API load
    - Low values (1-2s): Maximum responsiveness for user actions
    - High values (3-5s): Responsive but more conservative on API calls
    - Automatically reverts to normal scan interval after TEMP_REFRESH_DURATION
    
    LOW INTERVALS (Fast Polling):
    - 1 second:   Very fast (max 60 API calls/minute for this operation)
      → Immediate feedback, highest API usage
      → Best for: Real-time position tracking, urgent actions
    - 2 seconds:  Standard fast (max 30 API calls/minute for this operation)
      → Balanced feedback, moderate API usage
      → Best for: Cover position tracking, temperature monitoring
    
    HIGH INTERVALS (Conservative Fast Polling):
    - 3 seconds:  Conservative fast (max 20 API calls/minute)
      → Reasonable feedback, lower API usage
    - 5 seconds:  Slow fast (max 12 API calls/minute)
      → Minimal extra load, almost standard polling
      → Best for: Battery-conscious operations, API-limited scenarios
    
    RECOMMENDED VALUES BY USE CASE:
    - Cover position tracking: 1-2 seconds for smooth UI updates
    - Temperature monitoring: 2-3 seconds for rapid feedback
    - General operations: 2 seconds (default balance)
    - Battery-conscious: 3-5 seconds for lower load
    
    API LOAD CALCULATION:
    - Frequency = 60 / interval_in_seconds
    - 1s interval = 60 calls/min, 2s = 30/min, 3s = 20/min, 5s = 12/min
        Args:
            value: Value to validate (int or convertible)
        Returns:
            Validated interval in seconds
        Raises:
            ValueError if value is out of range or out of bounds
        See Also:
            DEFAULT_TEMP_REFRESH_INTERVAL for default (2 seconds)
        See Also:
            validate_temp_refresh_duration for matching duration configuration
        Note:
            Low values = fast polling (responsive), High values = conservative
        Note:
            Used after commands like cover position changes to provide feedback
    """
    try:
        interval = int(value)
        if not (1 <= interval <= 5):
            raise ValueError(f"Temp refresh interval must be 1-5 seconds, got {interval}")
        return interval
    except (ValueError, TypeError) as err:
        raise ValueError(f"Invalid temp refresh interval: {err}") from err


def validate_temp_refresh_duration(value: Any) -> int:
    """ Validate fast polling duration (temporary refresh window).
    
    Determines how long fast polling (temp_refresh_interval) remains active
    after an action is triggered. Balances user responsiveness with API efficiency.
    
    FAST POLLING DURATION (30-120 seconds):
    - Window when fast polling is active after cover/action trigger
    - Provides quick feedback for user operations
    - Low values (30s): Quick revert to normal, less API usage
    - Default (120s): Extended responsiveness window (2 minutes)
    - High values (120s): Maximum responsiveness, more API calls
    
    DURATION EFFECTS:
    - 30 seconds:   Brief fast polling, quick efficiency revert
    - 60 seconds:   Balanced responsiveness window
    - 90 seconds:   Extended responsiveness for slower operations
    - 120 seconds:  Maximum 2-minute fast polling window (default)
    
    RECOMMENDED VALUES:
    - Quick response required: 30-60 seconds (energy efficient)
    - Standard operations: 90-120 seconds (good balance)
    - Slow/complex operations: 120 seconds (maximum responsiveness)
    
    INTERACTION WITH INTERVAL:
    - If temp_refresh_interval=1s and temp_refresh_duration=120s:
      → 120 API calls during fast polling window (max ~1 per second)
    - If temp_refresh_interval=2s and temp_refresh_duration=120s:
      → 60 API calls during fast polling window (max ~0.5 per second)
        Args:
            value: Value to validate (int or convertible)
        Returns:
            Validated duration in seconds
        Raises:
            ValueError if value is out of range or out of bounds
        See Also:
            DEFAULT_TEMP_REFRESH_DURATION
        See Also:
            validate_temp_refresh_interval for matching interval configuration
        Note:
            Determines how long to maintain fast polling (1-5s interval)
    """
    try:
        duration = int(value)
        if not (30 <= duration <= 120):
            raise ValueError(
                f"Fast polling duration must be 30-120 seconds (low=quick revert, high=extended), got {duration}"
            )
        return duration
    except (ValueError, TypeError) as err:
        raise ValueError(f"Invalid fast polling duration: {err}") from err


def validate_port(value: Any) -> int:
    """ Validate network port number.
    
    Ensures port is in valid range for network communication.
        Args:
            value: Port number to validate (int or convertible)
        Returns:
            Validated port number
        Raises:
            ValueError if value is out of range
        Note:
            Standard Freebox API port is 443 (HTTPS)
    """
    try:
        port = int(value)
        if not (1 <= port <= 65535):
            raise ValueError(f"Port must be 1-65535, got {port}")
        return port
    except (ValueError, TypeError) as err:
        raise ValueError(f"Invalid port number: {err}") from err


def validate_host(value: str) -> str:
    """ Validate host address or IP.
    
    Basic validation for hostname or IP address format.
        Args:
            value: Host string to validate
        Returns:
            Validated host string
        Raises:
            ValueError if format seems invalid
        Note:
            Allows: hostname, IPv4, IPv6 formats
    """
    if not isinstance(value, str):
        raise ValueError(f"Host must be string, got {type(value).__name__}")
    
    host = value.strip()
    if not host:
        raise ValueError("Host cannot be empty")
    
    if len(host) > 255:
        raise ValueError(f"Host too long ({len(host)} > 255 chars)")
    
    # Basic check for valid characters
    if not re.match(r"^[a-zA-Z0-9:.\-\[\]]+$", host):
        raise ValueError(f"Host contains invalid characters: '{host}'")
    
    return host


def get_validation_bounds() -> dict[str, dict[str, int | str]]:
    """ Get all validation bounds for configuration parameters.
    
    Returns a dictionary describing the valid ranges for all
    configurable parameters.
        Returns:
            Dictionary with parameter bounds and descriptions
        Example:
    bounds = get_validation_bounds()
    print(bounds['scan_interval'])
    # Output: {'min': 10, 'max': 300, 'default': 30, 'unit': 'seconds'}
    """
    return {
        "scan_interval": {
            "min": 10,
            "max": 300,
            "default": 30,
            "unit": "seconds",
            "description": "Normal polling interval"
        },
        "reboot_interval_days": {
            "min": 0,
            "max": 30,
            "default": 7,
            "unit": "days",
            "description": "Scheduled reboot frequency (0 disables)"
        },
        "reboot_time": {
            "format": "HH:MM",
            "default": "03:00",
            "timezone": "local",
            "description": "Scheduled reboot time (24-hour format)"
        },
        "temp_refresh_interval": {
            "min": 1,
            "max": 5,
            "default": 2,
            "unit": "seconds",
            "description": "Fast polling interval (after commands)"
        },
        "temp_refresh_duration": {
            "min": 30,
            "max": 120,
            "default": 120,
            "unit": "seconds",
            "description": "Fast polling duration (after commands)"
        },
        "port": {
            "min": 1,
            "max": 65535,
            "default": 443,
            "unit": "port number",
            "description": "Freebox API port"
        }
    }
