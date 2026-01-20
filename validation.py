"""
@file validation.py
@author Freebox Home Contributors
@brief Configuration validation helpers for Freebox integration.
@version 1.3.0

This module provides validation functions and utility helpers for
configuration values, ensuring they fall within safe operational bounds
and conform to required formats.

@section helpers Validation Helpers
- validate_scan_interval(): Validates polling frequency (10-300s)
- validate_reboot_interval(): Validates reboot frequency (0-30 days)
- validate_reboot_time(): Validates time format (HH:MM, 24-hour)
- validate_temp_refresh_interval(): Validates fast poll frequency (1-5s)
- validate_temp_refresh_duration(): Validates fast poll duration (30-120s)
- validate_port(): Validates network port (1-65535)

@see config_flow for integration with Home Assistant config flow
"""
from __future__ import annotations

import re
from typing import Any


def validate_scan_interval(value: Any) -> int:
    """
    @brief Validate normal polling scan interval.
    
    Ensures the polling interval is within safe bounds to prevent
    API overload while maintaining responsiveness.
    
    @param[in] value Value to validate (int or convertible)
    @return Validated interval in seconds
    @throw ValueError if value is out of range
    
    @see DEFAULT_SCAN_INTERVAL
    """
    try:
        interval = int(value)
        if not (10 <= interval <= 300):
            raise ValueError(f"Scan interval must be 10-300 seconds, got {interval}")
        return interval
    except (ValueError, TypeError) as err:
        raise ValueError(f"Invalid scan interval: {err}") from err


def validate_reboot_interval(value: Any) -> int:
    """
    @brief Validate scheduled reboot interval.
    
    Ensures reboot frequency is reasonable (0 disables, 1-30 enables).
    
    @param[in] value Value to validate (int or convertible)
    @return Validated interval in days
    @throw ValueError if value is out of range
    
    @see DEFAULT_REBOOT_INTERVAL_DAYS
    """
    try:
        interval = int(value)
        if not (0 <= interval <= 30):
            raise ValueError(f"Reboot interval must be 0-30 days, got {interval}")
        return interval
    except (ValueError, TypeError) as err:
        raise ValueError(f"Invalid reboot interval: {err}") from err


def validate_reboot_time(value: str) -> str:
    """
    @brief Validate scheduled reboot time format.
    
    Ensures time is in valid 24-hour HH:MM format.
    
    @param[in] value Time string to validate
    @return Validated time string (HH:MM)
    @throw ValueError if format is invalid
    
    @note Valid formats: "00:00" to "23:59"
    """
    if not isinstance(value, str):
        raise ValueError(f"Reboot time must be string, got {type(value).__name__}")
    
    if not re.match(r"^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$", value.strip()):
        raise ValueError(
            f"Reboot time must be in HH:MM format (24-hour), got '{value}'"
        )
    return value.strip()


def validate_temp_refresh_interval(value: Any) -> int:
    """
    @brief Validate fast polling interval (temporary refresh).
    
    Ensures temporary polling frequency is high enough for responsiveness
    while not overwhelming the API with requests.
    
    @param[in] value Value to validate (int or convertible)
    @return Validated interval in seconds
    @throw ValueError if value is out of range
    
    @see DEFAULT_TEMP_REFRESH_INTERVAL
    @note Used after commands like cover position changes
    """
    try:
        interval = int(value)
        if not (1 <= interval <= 5):
            raise ValueError(f"Temp refresh interval must be 1-5 seconds, got {interval}")
        return interval
    except (ValueError, TypeError) as err:
        raise ValueError(f"Invalid temp refresh interval: {err}") from err


def validate_temp_refresh_duration(value: Any) -> int:
    """
    @brief Validate fast polling duration (temporary refresh).
    
    Ensures fast polling doesn't run indefinitely, preventing unnecessary
    API load after command completion.
    
    @param[in] value Value to validate (int or convertible)
    @return Validated duration in seconds
    @throw ValueError if value is out of range
    
    @see DEFAULT_TEMP_REFRESH_DURATION
    @note Determines how long to maintain fast polling (1-5s interval)
    """
    try:
        duration = int(value)
        if not (30 <= duration <= 120):
            raise ValueError(f"Temp refresh duration must be 30-120 seconds, got {duration}")
        return duration
    except (ValueError, TypeError) as err:
        raise ValueError(f"Invalid temp refresh duration: {err}") from err


def validate_port(value: Any) -> int:
    """
    @brief Validate network port number.
    
    Ensures port is in valid range for network communication.
    
    @param[in] value Port number to validate (int or convertible)
    @return Validated port number
    @throw ValueError if value is out of range
    
    @note Standard Freebox API port is 443 (HTTPS)
    """
    try:
        port = int(value)
        if not (1 <= port <= 65535):
            raise ValueError(f"Port must be 1-65535, got {port}")
        return port
    except (ValueError, TypeError) as err:
        raise ValueError(f"Invalid port number: {err}") from err


def validate_host(value: str) -> str:
    """
    @brief Validate host address or IP.
    
    Basic validation for hostname or IP address format.
    
    @param[in] value Host string to validate
    @return Validated host string
    @throw ValueError if format seems invalid
    
    @note Allows: hostname, IPv4, IPv6 formats
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
    """
    @brief Get all validation bounds for configuration parameters.
    
    Returns a dictionary describing the valid ranges for all
    configurable parameters.
    
    @return Dictionary with parameter bounds and descriptions
    
    @example
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
