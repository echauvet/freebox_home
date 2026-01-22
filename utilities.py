"""Utility functions for caching, performance monitoring, and data access.

Provides CachedValue for data caching, PerformanceTimer for operation timing,
and safe_get() for safe nested dictionary access.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Generic, Optional, TypeVar
import time

_LOGGER = logging.getLogger(__name__)

T = TypeVar('T')


class CachedValue(Generic[T]):
    """ Generic value caching with TTL expiration.
    
    Stores a value with automatic expiration after specified time.
    Useful for caching expensive operations with time-based invalidation.
        Example:
    cache = CachedValue[int](60)  # 60 second TTL
    cache.set(42)
    value = cache.get()  # Returns 42 if not expired
    """

    def __init__(self, ttl_seconds: int = 60) -> None:
        """ Initialize cache with TTL.
        Args:
            ttl_seconds: Time-to-live in seconds
        """
        self._value: Optional[T] = None
        self._expiry: Optional[datetime] = None
        self._ttl_seconds: int = ttl_seconds

    def set(self, value: T) -> None:
        """ Store value with expiry time.
        Args:
            value: Value to cache
        """
        self._value = value
        self._expiry = datetime.now(timezone.utc) + timedelta(
            seconds=self._ttl_seconds
        )
        _LOGGER.debug("Cache updated, expires in %d seconds", self._ttl_seconds)

    def get(self) -> Optional[T]:
        """ Retrieve cached value if not expired.
        Returns:
            Cached value or None if expired/not set
        """
        if self._value is None or self._expiry is None:
            return None
        
        if datetime.now(timezone.utc) > self._expiry:
            _LOGGER.debug("Cache expired, clearing")
            self._value = None
            self._expiry = None
            return None
        
        return self._value

    def is_expired(self) -> bool:
        """ Check if cache is expired.
        Returns:
            True if expired or never set
        """
        return self.get() is None


class PerformanceTimer:
    """ Context manager for measuring operation performance.
    
    Measures execution time and logs results with configurable levels.
    Useful for identifying performance bottlenecks.
        Example:
    with PerformanceTimer("API call") as timer:
        result = await api.get_data()
        timer.checkpoint("data fetch complete")
    # Logs: "API call: 245ms"
    """

    def __init__(self, name: str, warn_threshold_ms: float = 1000) -> None:
        """ Initialize timer.
        Args:
            name: Operation name for logging
        Args:
            warn_threshold_ms: Log warning if exceeds this time
        """
        self.name = name
        self.warn_threshold_ms = warn_threshold_ms
        self.start_time: float = 0.0
        self.checkpoints: list[tuple[str, float]] = []

    def __enter__(self) -> PerformanceTimer:
        """Start timing."""
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Stop timing and log result."""
        elapsed_ms = (time.time() - self.start_time) * 1000
        
        if elapsed_ms > self.warn_threshold_ms:
            _LOGGER.warning(
                "%s took %.1fms (threshold: %.1fms)",
                self.name,
                elapsed_ms,
                self.warn_threshold_ms
            )
        else:
            _LOGGER.debug("%s completed in %.1fms", self.name, elapsed_ms)
        
        if self.checkpoints:
            _LOGGER.debug("Checkpoints: %s", self.checkpoints)

    def checkpoint(self, name: str) -> None:
        """ Mark checkpoint for interval measurement.
        Args:
            name: Checkpoint name
        """
        elapsed_ms = (time.time() - self.start_time) * 1000
        self.checkpoints.append((name, elapsed_ms))


def safe_get(dictionary: dict[str, Any], *keys: str, default: Any = None) -> Any:
    """ Safe nested dictionary access.
    
    Safely navigate nested dictionaries without KeyError/TypeError.
        Args:
            dictionary: Root dictionary to access
        Args:
            keys: Nested keys to traverse
        Args:
            default: Value to return if key path not found
        Returns:
            Value at path or default
        Example:
    data = {"user": {"profile": {"name": "John"}}}
    name = safe_get(data, "user", "profile", "name")  # "John"
    age = safe_get(data, "user", "age", default="unknown")  # "unknown"
    """
    current = dictionary
    for key in keys:
        if isinstance(current, dict):
            current = current.get(key)
            if current is None:
                return default
        else:
            return default
    return current


def format_timestamp(timestamp: float | int, format_str: str = "%Y-%m-%d %H:%M:%S") -> str:
    """ Format Unix timestamp for display.
        Args:
            timestamp: Unix timestamp (seconds since epoch)
        Args:
            format_str: strftime format string
        Returns:
            Formatted timestamp string
        Example:
    ts = 1705779600
    formatted = format_timestamp(ts)  # "2024-01-20 15:00:00"
    """
    try:
        dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
        return dt.strftime(format_str)
    except (ValueError, OSError, OverflowError) as err:
        _LOGGER.warning("Failed to format timestamp %s: %s", timestamp, err)
        return "N/A"


def parse_uptime(uptime_seconds: int) -> str:
    """ Parse uptime in seconds to human-readable format.
        Args:
            uptime_seconds: Uptime duration in seconds
        Returns:
            Human-readable uptime string
        Example:
    uptime_str = parse_uptime(345600)  # "4 days, 0 hours"
    """
    days = uptime_seconds // 86400
    hours = (uptime_seconds % 86400) // 3600
    minutes = (uptime_seconds % 3600) // 60
    
    parts = []
    if days > 0:
        parts.append(f"{days} day{'s' if days != 1 else ''}")
    if hours > 0:
        parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
    if minutes > 0 or not parts:
        parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
    
    return ", ".join(parts)


def truncate_string(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """ Truncate long strings with ellipsis.
        Args:
            text: String to truncate
        Args:
            max_length: Maximum length before truncation
        Args:
            suffix: String to append if truncated
        Returns:
            Truncated string
        Example:
    long = "This is a very long text..."
    short = truncate_string(long, 20)  # "This is a very l..."
    """
    if len(text) <= max_length:
        return text
    return text[: max_length - len(suffix)] + suffix


def get_performance_stats() -> dict[str, Any]:
    """ Get integration performance statistics.
    
    Returns timing information for monitoring performance
    and identifying bottlenecks.
        Returns:
            Dictionary with performance metrics
        Note:
            Implementation can track various metrics:
    - Average API response time
    - Cache hit rates
    - Update frequency
    - Error rates
    """
    return {
        "api_calls_total": 0,
        "api_call_errors": 0,
        "avg_response_time_ms": 0,
        "cache_hits": 0,
        "cache_misses": 0,
        "last_update": None,
    }
